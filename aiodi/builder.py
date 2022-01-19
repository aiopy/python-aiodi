from abc import ABC
from glob import glob
from inspect import Parameter, signature
from os import getenv
from os.path import abspath, dirname
from pathlib import Path
from random import shuffle
from re import finditer
from sys import executable, modules
from typing import (
    Any,
    Dict,
    List,
    Match,
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
from .toml import TOMLDecoder, lazy_toml_decoder

_DEFAULTS = {
    'FILENAMES': [
        './pyproject.toml',
        './services.toml',
        './../pyproject.toml',
        './../services.toml',
    ],
    'SERVICE': ...,
    'VARIABLE': ...,
}

_VARIABLE_METADATA_REGEX = r"%(static|env|var)\((str:|int:|float:|bool:)?([\w]+)(,\s{1}'.*?')?\)%"
_SERVICE_AUTOREGISTRATION_EXCLUDE_REGEX = r"^([.\w/]+)?({[\w/.*,]+})?$"


class _RawData(NamedTuple):
    variables: Dict[str, Any]
    services: Dict[str, Any]


class _VariableMatchMetadata(NamedTuple):
    source_kind: str
    type: Type[Any]
    source_name: str
    default: Any
    match: Match


class _VariableMetadata(NamedTuple):
    name: str
    value: Any
    matches: List[_VariableMatchMetadata]


class _ServiceDefaults(NamedTuple):
    project_dir: str = None  # type: ignore
    autowire: bool = True
    autoconfigure: bool = True
    autoregistration: Dict[str, Optional[str]] = {
        'resource': None,
        'exclude': None,
    }


class _ServiceParameterMetadata(NamedTuple):
    name: str
    source_kind: str
    type: Type[Any]
    default: Any


class _ServiceMetadata(NamedTuple):
    name: str
    type: Type[Any]
    clazz: Type[Any]
    arguments: Dict[str, Any]
    params: List[_ServiceParameterMetadata]
    defaults: _ServiceDefaults


class _ServiceExcludeMetadata(NamedTuple):
    left: str
    right: List[str]


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
    _debug: bool
    _tool_key: str
    _cwd: Path
    _filepaths: List[Path]
    _toml_decoder: Optional[TOMLDecoder]
    _variables_key: str
    _variables: Dict[str, Any]
    _services: Dict[str, Any]
    _services_defaults: _ServiceDefaults

    def __init__(
        self,
        filenames: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        *,
        debug: bool = False,
        tool_key: str = 'aiodi',
        var_key: str = 'env',
        toml_decoder: Optional[TOMLDecoder] = None
    ) -> None:
        self._debug = debug
        self._tool_key = tool_key
        self._cwd = self._find_cwd(cwd=cwd)
        self._filepaths = self._parse_filepaths(
            cwd=self._cwd, filenames=_DEFAULTS['FILENAMES'] if len(filenames or []) == 0 else filenames  # type: ignore
        )
        self._toml_decoder = toml_decoder
        self._variables_key = str('env' if var_key is None or len(var_key) == 0 else var_key)
        self._variables = {}
        self._services = {}
        self._services_defaults = _ServiceDefaults()

    def load(self) -> Container:
        raw = self._raw_toml_load()

        self._parse_variables_wrapper(raw_variables=raw.variables)

        self._services.setdefault(self._variables_key, self._variables)

        self._parse_services_wrapper(raw_services=raw.services)

        return Container(items=[(key, val, {}) for key, val in self._services.items()])

    @staticmethod
    def _find_cwd(cwd: Optional[str]) -> Path:
        if cwd:
            return Path(cwd)
        try:
            main_file = abspath(modules['__main__'].__file__)  # type: ignore
        except Exception:
            main_file = executable
        return Path(dirname(main_file))  # type: ignore

    @staticmethod
    def _parse_filepaths(cwd: Path, filenames: List[str]) -> List[Path]:
        filepaths: List[Path] = []
        for filename in filenames:
            parts_to_remove = len(([part for part in Path(filename).parts if part == '..']))
            filename_ = '/'.join(
                [
                    *(cwd.parts if parts_to_remove == 0 else cwd.parts[:-parts_to_remove]),
                    *Path(filename).parts[parts_to_remove:],
                ]
            )
            if filename_.startswith('//'):
                filename_ = filename_[1:]
            filepaths.append(Path(filename_))
        return filepaths

    def _sanitize_raw_data(self, raw: MutableMapping[str, Any]) -> _RawData:
        data = raw.get('tool', {}).get(self._tool_key, {})
        data.setdefault('variables', {})
        data.setdefault('services', {})
        data.get('services').setdefault('_defaults', self._services_defaults._asdict())
        project_dir = data.get('services').get('_defaults').get('project_dir')
        if project_dir is None or len(project_dir) == 0:
            data.get('services').get('_defaults')['project_dir'] = self._cwd
        else:
            parts_to_remove = len([part for part in Path(project_dir).parts if part == '..'])
            project_dir = '/'.join(self._cwd.parts[:-parts_to_remove])
            if project_dir.startswith('//'):
                project_dir = project_dir[1:]
            data.get('services').get('_defaults')['project_dir'] = project_dir
            self._cwd = Path(project_dir)
        rawdata = _RawData(variables=data.get('variables'), services=data.get('services'))
        self._services_defaults = _ServiceDefaults(**rawdata.services.get('_defaults', {}))
        if '_defaults' in rawdata.services:
            del rawdata.services['_defaults']
        return rawdata

    def _raw_toml_load(self) -> _RawData:
        if not self._toml_decoder:
            self._toml_decoder = lazy_toml_decoder()
        for filepath in self._filepaths:
            if filepath.is_file() and filepath.exists():
                raw = self._toml_decoder(filepath)
                return self._sanitize_raw_data(raw=raw)

        raise FileNotFoundError('Missing .toml file to load dependencies')

    def _parse_variables_wrapper(self, raw_variables: Dict[str, Any]) -> None:
        variables = dict(
            [(key, (self._get_variable_metadata(key=key, val=val), 0)) for key, val in raw_variables.items()]
        )
        variable_limit_retries = pow(len(variables.keys()), 3)
        while len(variables.keys()) > 0:
            try:
                self._parse_variables(variables=variables)
            except VariableResolutionPostponed as err:
                if self._debug:
                    logger.debug(err.__str__())
                if err.times() == variable_limit_retries:
                    raise InterruptedError(
                        'Reached limit of retries ({0}) per variable <{1}>!'.format(variable_limit_retries, err.key())
                    )
                if err.key() not in variables:
                    variables_list = list({**variables, err.key(): (err.value(), err.times())}.items())
                else:
                    variables_list = list(variables.items())
                shuffle(variables_list)  # avoid re-processing same dependency
                variables = dict(variables_list)
            finally:
                for key in self._variables.keys():
                    if key in variables.keys():
                        del variables[key]

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

    def _get_service_metadata_from_autoload(self, name: str, defaults: _ServiceDefaults) -> _ServiceMetadata:
        return self._get_service_metadata(
            key=name,
            val={
                'type': name,
                'class': name,
                'arguments': {},
                '_defaults': {},
            },
            defaults=_ServiceDefaults(
                project_dir=defaults.project_dir,
                autowire=defaults.autowire,
                autoconfigure=defaults.autoconfigure,
                autoregistration={},
            ),
        )

    @staticmethod
    def _find_service_exclude_matches(val: Any) -> List[Match]:
        return list((finditer(_SERVICE_AUTOREGISTRATION_EXCLUDE_REGEX, val) if isinstance(val, str) else {}) or {})

    def _get_service_exclude_metadata(self, raw_exclude: str, project_dir: str) -> Optional[_ServiceExcludeMetadata]:
        exclude_matches = self._find_service_exclude_matches(val=raw_exclude)
        if len(exclude_matches) == 0:
            return None
        exclude_groups = exclude_matches[0].groups()
        left = project_dir if exclude_groups[0] is None else project_dir + '/' + exclude_groups[0]
        left = '/'.join(list(Path(str(Path(left).absolute()).replace('../', '')).parts[-len(Path(left).parts) :]))[1:]
        rights: List[str] = []
        for right in ('{}' if exclude_groups[1] is None else exclude_groups[1])[1:-1].split(','):
            rights += glob(left + '/' + right)
        return _ServiceExcludeMetadata(
            left=left,
            right=list(set(rights)),
        )

    def _prepare_services_to_parse(self, raw_services: Dict[str, Any]) -> Dict[str, Tuple[_ServiceMetadata, int]]:
        services: Dict[str, Tuple[_ServiceMetadata, int]] = {}
        for key, val in raw_services.items():
            defaults = self._get_service_defaults(val=val)
            resource = defaults.autoregistration['resource'] or ''
            if resource:
                excludes: List[str] = []
                if defaults.autoregistration['exclude']:
                    exclude_metadata = self._get_service_exclude_metadata(
                        raw_exclude=(defaults.autoregistration['exclude'] or ''), project_dir=defaults.project_dir or ''
                    )
                    if exclude_metadata:
                        excludes = (
                            [exclude_metadata.left] if len(exclude_metadata.right) == 0 else exclude_metadata.right
                        )

                names: List[str] = []
                resources: List[str] = [resource]
                if resource.endswith('/*'):
                    resources = [
                        include.replace(defaults.project_dir + '/', '', 1)
                        for include in glob(defaults.project_dir + '/' + resource)
                        if not include.endswith('__pycache__') and not include.endswith('.pyc')
                    ]
                for include in resources:
                    names += [
                        name
                        for name, mod in import_module_and_get_attrs(name=include, excludes=excludes).items()
                        if hasattr(mod, '__mro__') and not mod.__mro__[1:][0] is ABC  # avoid loading interfaces
                    ]
                for name in set(names):
                    services[name] = (self._get_service_metadata_from_autoload(name=name, defaults=defaults), 0)
            else:
                metadata = self._get_service_metadata(key=key, val=val, defaults=defaults)
                if hasattr(metadata.type, '__mro__') and metadata.type.__mro__[1:][0] is ABC:
                    raise TypeError('Can not instantiate abstract class <{0}>!'.format(metadata.name))
                services[key] = (metadata, 0)
        return services

    def _parse_services_wrapper(self, raw_services: Dict[str, Any]) -> None:
        services = self._prepare_services_to_parse(raw_services=raw_services)
        service_limit_retries = pow(len(services.keys()), 3)
        while len(services.keys()) > 0:
            try:
                self._parse_services(services=services)
            except ServiceResolutionPostponed as err:
                if self._debug:
                    logger.debug(err.__str__())
                if err.times() == service_limit_retries:
                    raise InterruptedError(
                        'Reached limit of retries ({0}) per service <{1}>!'.format(service_limit_retries, err.key())
                    )
                if err.key() not in services:
                    services_list = list({err.key(): (err.value(), err.times()), **services}.items())
                else:
                    services_list = list(services.items())
                shuffle(services_list)  # avoid re-processing same dependency
                services = dict(services_list)
            finally:
                for key in self._services.keys():
                    if key in services.keys():
                        del services[key]

    def _parse_services(self, services: Dict[str, Tuple[_ServiceMetadata, int]]) -> None:
        for name, (metadata, times) in services.items():
            self._services.setdefault(
                name,
                self._parse_service(
                    service_metadata=metadata,
                    retries=times,
                ),
            )

    @staticmethod
    def _define_service_type(name: str, typ: str, cls: str) -> Tuple[Type[Any], Type[Any]]:
        if typ is _DEFAULTS['SERVICE'] and cls is _DEFAULTS['SERVICE']:
            cls = typ = import_module_and_get_attr(name=name)  # type: ignore
            return typ, cls  # type: ignore

        if typ is not _DEFAULTS['SERVICE']:
            typ = import_module_and_get_attr(name=typ)  # type: ignore
        if cls is not _DEFAULTS['SERVICE']:
            cls = import_module_and_get_attr(name=cls)  # type: ignore

        if typ is _DEFAULTS['SERVICE']:
            try:
                typ = import_module_and_get_attr(name=name)  # type: ignore
            except Exception:
                typ = cls
        if cls is _DEFAULTS['SERVICE']:
            cls = typ

        if cls is not typ and not issubclass(signature(cls).return_annotation or cls, typ):  # type: ignore
            raise TypeError('Class <{0}> return type must be <{1}>'.format(cls, typ))

        return typ, cls  # type: ignore

    def _get_service_defaults(self, val: Any) -> _ServiceDefaults:
        has_defaults = isinstance(val, dict) and '_defaults' in val
        if has_defaults:
            val['_defaults'].setdefault('project_dir', self._services_defaults.project_dir)
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
                        'svc'
                        if str(param[0]) in kwargs and kwargs[str(param[0])].startswith('@')
                        else (
                            'arg'
                            if str(param[0]) in kwargs
                            else (
                                'typ'
                                if param[1].default is Parameter.empty and not is_primitive(param[1].annotation)
                                else 'static'
                            )
                        )
                    ),
                    type=param[1].annotation,
                    default=(
                        kwargs[str(param[0])]
                        if str(param[0]) in kwargs and kwargs[str(param[0])].startswith('@')
                        else None
                        if param[1].default is Parameter.empty
                        else param[1].default
                    ),
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
                services = [svc for svc in self._services.values() if isinstance(svc, param.type)]
                if len(services) == 1:
                    param_val = services[0]
                else:
                    raise ServiceResolutionPostponed(
                        key='.'.join([param.type.__module__, param.type.__name__]),
                        value=service_metadata,
                        times=retries + 1,
                    )
            # cast primitive value
            if param_val is not None and is_primitive(param.type):
                param_val = param.type(param_val)
            parameters.setdefault(param.name, param_val)
        return service_metadata.clazz(**parameters)
