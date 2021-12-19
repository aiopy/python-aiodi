from inspect import Parameter, signature
from os import getenv
from pathlib import Path
from re import Match, finditer
from typing import (
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    NamedTuple,
    Optional,
    Tuple,
    Type,
)

from .container import Container
from .helpers import (
    import_module_and_get_attr,
    import_module_and_get_attrs,
    is_primitive,
)
from .logger import logger

_DEFAULTS = {
    'FILENAMES': [
        './pyproject.toml',
        './services.toml',
        './../pyproject.toml',
        './../services.toml',
    ],
    'SERVICE': ...,
    'SERVICE_DEFAULTS': {
        'autowire': True,
        'autoconfigure': True,
        'autoregistration': {
            'resource': None,
            'exclude': None,
        },
    },
    'VARIABLE': ...,
    'VARIABLE_KEY': 'env',
}

_VARIABLE_METADATA_REGEX = r"%(static|env|var)\((str:|int:|float:|bool:)?([\w]+)(,\s?'[\w\s]+')?\)%"

_VariableMatchMetadata = NamedTuple(
    '_VariableMatchMetadata', source_kind=str, type=Type[Any], source_name=str, default=Any, match=Match
)
_VariableMetadata = NamedTuple(
    '_VariableMetadata',
    name=str,
    value=Any,
    matches=List[_VariableMatchMetadata],
)

_ServiceDefaults = NamedTuple(
    '_ServiceDefaults',
    autowire=bool,
    autoconfigure=bool,
    autoregistration=Dict[str, Optional[str]],
)
_ServiceParameterMetadata = NamedTuple(
    '_ServiceParameterMetadata',
    name=str,
    source_kind=str,
    type=Type[Any],
    default=Any,
)
_ServiceMetadata = NamedTuple(
    '_ServiceMetadata',
    name=str,
    type=Type[Any],
    clazz=Type[Any],
    arguments=Dict[str, Any],
    params=List[_ServiceParameterMetadata],
    defaults=_ServiceDefaults,
)


class ValueResolutionPostponed(Exception):
    _key: str
    _value: Any
    _times: int

    def __init__(self, key: str, value: Any, times: int) -> None:
        super().__init__('<{0}> resolution postponed {1} time{2}'.format(key, times, 's' if times > 1 else ''))
        self._key = key
        self._value = value
        self._times = times

    def key(self) -> str:
        return self._key

    def value(self) -> Any:
        return self._value

    def times(self) -> int:
        return self._times


class VariableResolutionPostponed(ValueResolutionPostponed):
    def __init__(self, key: str, value: _VariableMetadata, times: int) -> None:
        super().__init__(key, value, times)


class ServiceResolutionPostponed(ValueResolutionPostponed):
    def __init__(self, key: str, value: _ServiceMetadata, times: int) -> None:
        super().__init__(key, value, times)


class VariableNotFound(Exception):
    def __init__(self, name: str) -> None:
        super().__init__('Variable <{0}> not found!'.format(name))


class ServiceNotFound(Exception):
    def __init__(self, name: str) -> None:
        super().__init__('Service <{0}> not found!'.format(name))


class ContainerBuilder:
    """Experimental"""

    _raw_load: Callable[[], MutableMapping[str, Any]]
    _variables_key: str
    _variables: Dict[str, Any]
    _services: Dict[str, Any]
    _services_defaults: _ServiceDefaults

    def __init__(
        self, filenames: List[str] = [], *, debug: bool = False, tool_key: str = 'aiodi', var_key: str = 'env'
    ) -> None:
        self._debug = debug

        if len(filenames) == 0:
            filenames = _DEFAULTS['FILENAMES']

        def _raw_load() -> MutableMapping[str, Any]:
            from toml import load

            for filename in filenames:
                if Path(filename).exists():
                    raw = load(filename)
                    data = raw.get('tool', {tool_key: {'variables': {}, 'services': {}}}).get(tool_key)
                    data.get('services').setdefault('_defaults', _DEFAULTS['SERVICE_DEFAULTS'])
                    return data

            raise FileNotFoundError('Missing file to load dependencies')

        self._raw_load = _raw_load
        self._variables_key = _DEFAULTS['VARIABLE_KEY'] if var_key is None or len(var_key) == 0 else var_key
        self._variables = {}
        self._services = {}
        self._services_defaults = _ServiceDefaults(**_DEFAULTS['SERVICE_DEFAULTS'])

    def load(self) -> Container:
        raw = self._raw_load()

        self._parse_variables_wrapper(raw_variables=raw.get('variables'))

        self._services.setdefault(self._variables_key, self._variables)

        svc_defaults = raw.get('services').get('_defaults')
        self._services_defaults = _ServiceDefaults(
            autowire=bool(svc_defaults['autowire']) if 'autowire' in svc_defaults else False,
            autoconfigure=bool(svc_defaults['autoconfigure']) if 'autoconfigure' in svc_defaults else False,
            autoregistration=svc_defaults['autoregistration'] if 'autoregistration' in svc_defaults else False,
        )
        del raw.get('services')['_defaults']

        self._parse_services_wrapper(raw_services=raw.get('services'))

        return Container(items=[(key, val, {}) for key, val in self._services.items()])

    def _parse_variables_wrapper(self, raw_variables: Dict[str, Any]) -> None:
        variables = dict(
            [(key, (self._get_variable_metadata(key=key, val=val), 0)) for key, val in raw_variables.items()]
        )
        variable_limit_retries = len(variables.keys())
        while len(variables.keys()) > 0:
            try:
                self._parse_variables(variables=variables)
                for key in self._variables.keys():
                    if key in variables.keys():
                        del variables[key]
            except VariableResolutionPostponed as err:
                if self._debug:
                    logger.debug(err.__str__())
                if err.times() == variable_limit_retries:
                    raise InterruptedError(
                        'Reached limit of retries ({0}) per variable <{1}>!'.format(variable_limit_retries, err.key())
                    )
                del variables[err.key()]
                variables[err.key()] = (err.value(), err.times())

    def _parse_variables(self, variables: Dict[str, Tuple[_VariableMetadata, int]]) -> None:
        for name, (metadata, times) in variables.items():
            self._variables.setdefault(
                name,
                self._parse_variable(
                    variable_metadata=metadata,
                    retries=times,
                ),
            )

    @staticmethod
    def _find_variable_metadata_matches(val: Any) -> List[Match]:
        return list((finditer(_VARIABLE_METADATA_REGEX, val) if isinstance(val, str) else {}) or {})

    @classmethod
    def _get_variable_metadata(cls, key: str, val: Any) -> _VariableMetadata:
        return _VariableMetadata(
            name=key,
            value=val,
            matches=[
                _VariableMatchMetadata(
                    source_kind=str(match.groups()[0]),
                    type=str if match.groups()[1] is None else globals()['__builtins__'][str(match.groups()[1])[:-1]],
                    source_name=str(match.groups()[2]),
                    default=None if match.groups()[3] is None else str(match.groups()[3])[3:-1],
                    match=match,
                )
                for match in cls._find_variable_metadata_matches(val=val)
                or cls._find_variable_metadata_matches(
                    val="%static({0}:{1}, '{2}')%".format(type(val).__name__, key, val)
                )
            ],
        )

    def _parse_variable(self, variable_metadata: _VariableMetadata, retries: int = -1) -> Any:
        values: List[str] = []
        for idx, metadata in enumerate(variable_metadata.matches):
            typ_val: str = ''
            if metadata.source_kind == 'static':
                typ_val = metadata.default
            elif metadata.source_kind == 'env':
                typ_val = getenv(metadata.source_name, metadata.default or '')
            elif metadata.source_kind == 'var':
                if metadata.source_name not in self._variables:
                    if retries != -1:
                        raise VariableResolutionPostponed(
                            key=variable_metadata.name, value=variable_metadata, times=retries + 1
                        )
                    else:
                        raise VariableNotFound(name=variable_metadata.name)
                typ_val = self._variables.get(metadata.source_name, metadata.default)
            # concatenate right side content per iteration
            values += (
                variable_metadata.value[
                    0 if idx == 0 else variable_metadata.matches[idx - 1].match.end() : metadata.match.start()
                ]
                + typ_val
            )
            # concatenate static content in last iteration
            if (len(variable_metadata) - 1) == idx:
                values += variable_metadata.value[metadata.match.end() :]
        value: Any = ''.join(values)
        if len(variable_metadata.matches) == 1:
            value = variable_metadata.matches[0].type(value)
        return value

    def _parse_services_wrapper(self, raw_services: Dict[str, Any]) -> None:
        services: Dict[str, Tuple[_ServiceMetadata, int]] = {}
        for key, val in raw_services.items():
            defaults = self._get_service_defaults(val=val)
            resource = defaults.autoregistration['resource'] or ''
            if resource and not resource.endswith('/*'):
                for name, _ in import_module_and_get_attrs(name=resource.replace('/', '.')).items():
                    services.setdefault(
                        name,
                        (
                            self._get_service_metadata(
                                key=name,
                                val={
                                    'type': name,
                                    'class': name,
                                    'arguments': {},
                                    '_defaults': {},
                                },
                                defaults=_ServiceDefaults(
                                    autowire=defaults.autowire,
                                    autoconfigure=defaults.autoconfigure,
                                    autoregistration={},
                                ),
                            ),
                            0,
                        ),
                    )
            else:
                services.setdefault(key, (self._get_service_metadata(key=key, val=val, defaults=defaults), 0))
        service_limit_retries = len(services.keys())
        while len(services.keys()) > 0:
            try:
                self._parse_services(services=services)
                for key in self._services.keys():
                    if key in services.keys():
                        del services[key]
            except ServiceResolutionPostponed as err:
                if self._debug:
                    logger.debug(err.__str__())
                if err.times() == service_limit_retries:
                    raise InterruptedError(
                        'Reached limit of retries ({0}) per service <{1}>!'.format(service_limit_retries, err.key())
                    )
                del services[err.key()]
                services[err.key()] = (err.value(), err.times())

    def _parse_services(self, services: Dict[str, Tuple[_ServiceMetadata, int]]) -> None:
        for name, (metadata, times) in services.items():
            self._services.setdefault(metadata.name, self._parse_service(service_metadata=metadata, retries=times))

    @staticmethod
    def _define_service_type(name: str, typ: str, cls: str) -> Tuple[Type[Any], Type[Any]]:
        if typ is _DEFAULTS['SERVICE'] and cls is _DEFAULTS['SERVICE']:
            cls = typ = import_module_and_get_attr(name=name)
            return typ, cls

        if typ is not _DEFAULTS['SERVICE']:
            typ = import_module_and_get_attr(name=typ)
        if cls is not _DEFAULTS['SERVICE']:
            cls = import_module_and_get_attr(name=cls)

        if typ is _DEFAULTS['SERVICE']:
            try:
                typ = import_module_and_get_attr(name=name)
            except Exception:
                typ = cls
        if cls is _DEFAULTS['SERVICE']:
            cls = typ

        if cls is not typ and not issubclass(signature(cls).return_annotation or cls, typ):
            raise TypeError('Class <{0}> return type must be <{1}>'.format(cls, typ))

        return typ, cls

    def _get_service_defaults(self, val: Any) -> _ServiceDefaults:
        has_defaults = isinstance(val, dict) and '_defaults' in val
        if has_defaults:
            val['_defaults'].setdefault('autoconfigure', False)
            val['_defaults'].setdefault(
                'autowire', self._services_defaults.autowire if self._services_defaults.autoconfigure else False
            )
            val['_defaults'].setdefault(
                'autoregistration',
                self._services_defaults.autoregistration if self._services_defaults.autoconfigure else {},
            )
            val['_defaults']['autoregistration'].setdefault(
                'resource',
                self._services_defaults.autoregistration['resource'] if self._services_defaults.autoconfigure else None,
            )
            val['_defaults']['autoregistration'].setdefault(
                'exclude',
                self._services_defaults.autoregistration['exclude'] if self._services_defaults.autoconfigure else None,
            )
        return _ServiceDefaults(**val['_defaults']) if has_defaults else self._services_defaults

    def _get_service_metadata(self, key: str, val: Any, defaults: _ServiceDefaults) -> _ServiceMetadata:
        typ, clazz = self._define_service_type(
            name=key,
            typ=val['type'] if isinstance(val, dict) and 'type' in val else _DEFAULTS['SERVICE'],
            cls=val['class'] if isinstance(val, dict) and 'class' in val else _DEFAULTS['SERVICE'],
        )
        kwargs = val['arguments'] if isinstance(val, dict) and 'arguments' in val else {}
        return _ServiceMetadata(
            name=key,
            type=typ,
            clazz=clazz,
            arguments=kwargs,
            params=[
                _ServiceParameterMetadata(
                    name=str(param[0]),
                    source_kind=(
                        'arg'
                        if str(param[0]) in kwargs
                        else (
                            'svc'
                            if isinstance(param[1].default, str) and param[1].default.startswith('@')
                            else (
                                'typ'
                                if param[1].default is Parameter.empty and not is_primitive(param[1].annotation)
                                else 'static'
                            )
                        )
                    ),
                    type=param[1].annotation,
                    default=None if param[1].default is Parameter.empty else param[1].default,
                )
                for param in signature(clazz).parameters.items()
            ],
            defaults=defaults,
        )

    def _parse_service(self, service_metadata: _ServiceMetadata, retries: int) -> Any:
        parameters: Dict[str, Any] = {}
        for param in service_metadata.params:
            param_val = param.default
            # extract raw value
            if param.source_kind == 'arg':
                param_val = self._parse_variable(
                    variable_metadata=self._get_variable_metadata(
                        key='@{0}:{1}'.format(service_metadata.name, param.name),
                        val=service_metadata.arguments[param.name],
                    ),
                )
            elif param.source_kind == 'svc':
                if param_val[1:] in self._services:
                    param_val = self._services[param_val[1:]]
                else:
                    raise ServiceResolutionPostponed(key=param_val[1:], value=service_metadata, times=retries + 1)
            elif param.source_kind == 'typ':
                if not service_metadata.defaults.autowire:
                    if self._debug:
                        logger.debug('Try enabling autowire')
                    raise ServiceNotFound(name=service_metadata.name)
                services = [svc for svc in self._services.values() if type(svc) is param.type]
                if len(services) == 1:
                    param_val = services[0]
                else:
                    raise ServiceNotFound(name=service_metadata.name)
            # cast primitive value
            if param_val is not None and is_primitive(param.type):
                param_val = param.type(param_val)
            parameters.setdefault(param.name, param_val)
        return service_metadata.clazz(**parameters)
