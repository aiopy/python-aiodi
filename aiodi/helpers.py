import typing
from importlib import import_module
from pkgutil import walk_packages
from types import ModuleType

typing_get_args = getattr(
    typing, 'get_args', lambda t: getattr(t, '__args__', ()) if t is not typing.Generic else typing.Generic
)
typing_get_origin = getattr(typing, 'get_origin', lambda t: getattr(t, '__origin__', None))

primitives = (bytes, bytearray, bool, int, float, str, dict, tuple, list, set, slice, map, zip)


def is_primitive(val: typing.Any) -> bool:
    return isinstance(val, primitives) or val in primitives


def is_object(val: typing.Any) -> bool:
    return isinstance(val, object) and not isinstance(val, type) and not is_primitive(val)


def is_simple(val: typing.Any) -> bool:
    return not is_object(val)


def is_optional(field: typing.Any) -> bool:  # pragma: no cover
    return typing_get_origin(field) is typing.Union and type(None) in typing_get_args(field)


def import_module_and_get_attr(name: str) -> typing.Type[typing.Any]:
    mod = '.'.join(name.split('.')[:-1])
    svc = name.split('.')[-1]
    globals()[mod] = import_module(name=mod)
    return getattr(globals()[mod], svc)


def _import_submodules(name: str, recursive: bool = True) -> typing.Dict[str, ModuleType]:
    package = import_module(name=name)
    results: typing.Dict[str, ModuleType] = {}
    for loader, name, is_pkg in walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name
        results[full_name] = import_module(full_name)
        if recursive and is_pkg:
            results.update(_import_submodules(full_name))
    return results


def import_module_and_get_attrs(name: str, recursive: bool = True) -> typing.Dict[str, typing.Type[typing.Any]]:
    results: typing.Dict[str, typing.Type[typing.Any]] = {}
    for name, module in _import_submodules(name=name, recursive=recursive).items():
        for key, svc in module.__dict__.items():
            if hasattr(svc, '__module__') and svc.__module__ == name:
                full_name = svc.__module__ + '.' + svc.__name__
                results[full_name] = svc
    return results
