from abc import ABC
from glob import glob
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Type, cast

from ..helpers import (
    import_module_and_get_attr,
    import_module_and_get_attrs,
    is_abstract,
    is_primitive,
    re_finditer,
)
from . import Resolver, ValueNotFound, ValueResolutionPostponed

_SERVICE_AUTOREGISTRATION_EXCLUDE_REGEX = r"^([.\w/]+)?({[\w/.*,]+})?$"
_SVC_DEFAULTS = ...


class ServiceDefaults(NamedTuple):
    project_dir: str = ''
    autowire: bool = True
    autoconfigure: bool = True
    autoregistration: Dict[str, Optional[str]] = {
        'resource': None,
        'exclude': None,
    }

    def resource(self) -> str:
        return self.autoregistration['resource'] or ''

    def exclude(self) -> str:
        return self.autoregistration['exclude'] or ''

    def has_resources(self) -> bool:
        if not self.resource():
            return False
        return True

    def compute_resources(self) -> List[str]:
        resources = [self.resource()]
        if not resources[0]:
            return []

        if resources[0].endswith('/*'):
            resources = [
                include.replace(self.project_dir + '/', '', 1)
                for include in glob(self.project_dir + '/' + resources[0])
                if not include.endswith('__pycache__') and not include.endswith('.pyc')
            ]

        return resources

    def compute_excludes(self) -> List[str]:
        raw_exclude: str = self.exclude()

        if not raw_exclude:
            return []

        exclude_matches = re_finditer(pattern=_SERVICE_AUTOREGISTRATION_EXCLUDE_REGEX, string=raw_exclude)
        if len(exclude_matches) == 0:
            return []

        exclude_groups = exclude_matches[0].groups()

        left = self.project_dir if exclude_groups[0] is None else self.project_dir + '/' + exclude_groups[0]
        left = '/'.join(list(Path(str(Path(left).absolute()).replace('../', '')).parts[-len(Path(left).parts) :]))[1:]

        rights: List[str] = []
        for right in ('{}' if exclude_groups[1] is None else exclude_groups[1])[1:-1].split(','):
            rights += glob(left + '/' + right)

        return [left] if len(rights) == 0 else rights

    def compute_services(
        self, resolver: Resolver[Any, Any], resources: List[str], excludes: List[str], extra: Dict[str, Any]
    ) -> Dict[str, Tuple['ServiceMetadata', int]]:
        names: List[str] = []
        for include in resources:
            names += [
                name
                for name, mod in import_module_and_get_attrs(name=include, excludes=excludes).items()
                if hasattr(mod, '__mro__') and not mod.__mro__[1:][0] is ABC  # avoid loading interfaces
            ]

        services: Dict[str, Tuple['ServiceMetadata', int]] = {}
        for name in set(names):
            services[name] = (
                resolver.extract_metadata(
                    data={
                        'key': name,
                        'val': {
                            'type': name,
                            'class': name,
                            'arguments': {},
                            '_defaults': {},
                        },
                        'defaults': ServiceDefaults(
                            project_dir=self.project_dir,
                            autowire=self.autowire,
                            autoconfigure=self.autoconfigure,
                        ),
                    },
                    extra=extra,
                ),
                0,
            )
        return services

    @classmethod
    def from_value(cls, val: Any, defaults: Optional['ServiceDefaults'] = None) -> 'ServiceDefaults':
        if not defaults:
            defaults = cls()
        has_defaults = isinstance(val, dict) and '_defaults' in val
        if has_defaults:
            val['_defaults'].setdefault('project_dir', defaults.project_dir)
            val['_defaults'].setdefault('autoconfigure', False)
            val['_defaults'].setdefault('autowire', defaults.autowire if defaults.autoconfigure else False)
            val['_defaults'].setdefault(
                'autoregistration',
                defaults.autoregistration if defaults.autoconfigure else {},
            )
            val['_defaults']['autoregistration'].setdefault(
                'resource',
                defaults.autoregistration['resource'] if defaults.autoconfigure else None,
            )
            val['_defaults']['autoregistration'].setdefault(
                'exclude',
                defaults.autoregistration['exclude'] if defaults.autoconfigure else None,
            )
        return cls(**val['_defaults']) if has_defaults else defaults


class ServiceMetadata(NamedTuple):
    name: str
    type: Type[Any]
    clazz: Type[Any]
    arguments: Dict[str, Any]
    params: List[Any]
    defaults: ServiceDefaults

    class ParameterMetadata(NamedTuple):  # type: ignore
        name: str
        source_kind: str
        type: Type[Any]
        default: Any

        @classmethod
        def from_param_inspected_and_args(
            cls, param: Tuple[str, Parameter], arguments: Dict[str, Any]
        ) -> 'ServiceMetadata.ParameterMetadata':
            return cls(
                name=str(param[0]),
                source_kind=(
                    'svc'
                    if str(param[0]) in arguments and arguments[str(param[0])].startswith('@')
                    else (
                        'arg'
                        if str(param[0]) in arguments
                        else (
                            'typ'
                            if param[1].default is Parameter.empty and not is_primitive(param[1].annotation)
                            else 'static'
                        )
                    )
                ),
                type=param[1].annotation,
                default=(
                    arguments[str(param[0])]
                    if str(param[0]) in arguments and arguments[str(param[0])].startswith('@')
                    else None
                    if param[1].default is Parameter.empty
                    else param[1].default
                ),
            )


class ServiceNotFound(ValueNotFound):
    def __init__(self, name: str) -> None:
        super().__init__(kind='Service', name=name)


class ServiceResolutionPostponed(ValueResolutionPostponed[ServiceMetadata]):
    pass


class ServiceResolver(Resolver[ServiceMetadata, Any]):
    @staticmethod
    def _define_service_type(name: str, typ: str, cls: str) -> Tuple[Type[Any], Type[Any]]:
        if typ is _SVC_DEFAULTS and cls is _SVC_DEFAULTS:  # type: ignore
            cls = typ = import_module_and_get_attr(name=name)  # type: ignore
            return typ, cls  # type: ignore

        if typ is not _SVC_DEFAULTS:  # type: ignore
            typ = import_module_and_get_attr(name=typ)  # type: ignore
        if cls is not _SVC_DEFAULTS:  # type: ignore
            cls = import_module_and_get_attr(name=cls)  # type: ignore

        if typ is _SVC_DEFAULTS:  # type: ignore
            try:
                typ = import_module_and_get_attr(name=name)  # type: ignore
            except Exception:
                typ = cls
        if cls is _SVC_DEFAULTS:  # type: ignore
            cls = typ

        if cls is not typ and not issubclass(signature(cls).return_annotation or cls, typ):  # type: ignore
            raise TypeError('Class <{0}> return type must be <{1}>'.format(cls, typ))

        return typ, cls  # type: ignore

    def extract_metadata(self, data: Dict[str, Any], extra: Dict[str, Any]) -> ServiceMetadata:  # pylint: disable=W0613
        key = cast(str, data.get('key'))
        val = data.get('val')
        defaults = cast(ServiceDefaults, data.get('defaults'))

        typ, clazz = self._define_service_type(
            name=key,
            typ=val['type'] if isinstance(val, dict) and 'type' in val else _SVC_DEFAULTS,
            cls=val['class'] if isinstance(val, dict) and 'class' in val else _SVC_DEFAULTS,
        )
        kwargs = val['arguments'] if isinstance(val, dict) and 'arguments' in val else {}
        return ServiceMetadata(
            name=key,
            type=typ,
            clazz=clazz,
            arguments=kwargs,
            params=[
                ServiceMetadata.ParameterMetadata.from_param_inspected_and_args(param=param, arguments=kwargs)
                for param in signature(clazz).parameters.items()
            ],
            defaults=defaults,
        )

    def parse_value(self, metadata: ServiceMetadata, retries: int, extra: Dict[str, Any]) -> Any:
        _variables = cast(Dict[str, Any], extra.get('variables'))
        _services = cast(Dict[str, Any], extra.get('services'))
        variable_resolver = cast(Resolver, extra.get('resolvers', {}).get('variable'))

        parameters: Dict[str, Any] = {}
        for param in metadata.params:
            param_val = param.default
            # extract raw value
            if param.source_kind == 'arg':
                param_val = variable_resolver.parse_value(
                    metadata=variable_resolver.extract_metadata(
                        data={
                            'key': '@{0}:{1}'.format(metadata.name, param.name),
                            'val': metadata.arguments[param.name],
                        },
                        extra=extra,
                    ),
                    retries=-1,
                    extra={'variables': _variables},
                )
            elif param.source_kind == 'svc':
                if param_val[1:] in _services:
                    param_val = _services[param_val[1:]]
                else:
                    raise ServiceResolutionPostponed(key=param_val[1:], value=metadata, times=retries + 1)
            elif param.source_kind == 'typ':
                if not metadata.defaults.autowire:
                    raise ServiceNotFound(name=metadata.name)
                services = [svc for svc in _services.values() if isinstance(svc, param.type)]
                if len(services) == 1:
                    param_val = services[0]
                else:
                    raise ServiceResolutionPostponed(
                        key='.'.join([param.type.__module__, param.type.__name__]),
                        value=metadata,
                        times=retries + 1,
                    )
            # cast primitive value
            if param_val is not None and is_primitive(param.type):
                param_val = param.type(param_val)
            parameters.setdefault(param.name, param_val)
        return metadata.clazz(**parameters)


def prepare_services_to_parse(
    resolver: Resolver[Any, Any], items: Dict[str, Any], extra: Dict[str, Any]
) -> Dict[str, Tuple['ServiceMetadata', int]]:
    _service_defaults = cast(ServiceDefaults, extra.get('_service_defaults'))

    services: Dict[str, Tuple['ServiceMetadata', int]] = {}
    for key, val in items.items():
        defaults = ServiceDefaults.from_value(val=val, defaults=_service_defaults)
        if defaults.has_resources():
            services.update(
                defaults.compute_services(
                    resolver=resolver,
                    resources=defaults.compute_resources(),
                    excludes=defaults.compute_excludes(),
                    extra=extra,
                )
            )
        else:
            metadata = resolver.extract_metadata(data={'key': key, 'val': val, 'defaults': defaults}, extra=extra)
            if is_abstract(metadata.type):
                raise TypeError('Can not instantiate abstract class <{0}>!'.format(metadata.name))
            services[key] = (metadata, 0)
    return services
