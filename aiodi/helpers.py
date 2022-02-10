import typing
from abc import ABC
from importlib import import_module
from pathlib import Path
from pkgutil import walk_packages
from re import finditer
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
    return typing_get_origin(field) is typing.Union and type(None) in typing_get_args(field)  # type: ignore


def import_module_and_get_attr(name: str) -> typing.Type[typing.Any]:
    name = name.replace('/', '.')
    mod = '.'.join(name.split('.')[:-1])
    svc = name.split('.')[-1]
    globals()[mod] = import_module(name=mod)
    return getattr(globals()[mod], svc)


def types_in_module(module: ModuleType) -> typing.List[typing.Type[typing.Any]]:
    items = module.__dict__
    return [items[key] for key in items if (isinstance(items[key], type) and items[key].__module__ == module.__name__)]


def import_submodules(path: str, recursive: bool, excludes: typing.List[Path]) -> typing.Dict[str, ModuleType]:
    full_name = path.replace('.py', '', 1).replace('/', '.')
    package = import_module(name=full_name)

    exclude_paths = [str(exclude) for exclude in excludes]
    includes: typing.List[typing.Tuple[Path, str, bool]] = []
    results: typing.Dict[str, ModuleType] = {}

    if hasattr(package, '__path__'):
        for file_finder, name, is_pkg in walk_packages(path=package.__path__):
            include = Path(file_finder.path)  # type: ignore
            include_absolute_path = str(Path(file_finder.path)) + '/' + name + ('' if is_pkg else '.py')  # type: ignore
            if include_absolute_path in exclude_paths:
                continue
            includes.append((include, name, is_pkg))
    else:
        results[full_name] = package

    for include, name, is_pkg in includes:
        full_name = package.__name__ + '.' + name
        results[full_name] = import_module(name=full_name)
        if recursive and is_pkg:
            results.update(import_submodules(path=full_name.replace('.', '/'), recursive=recursive, excludes=excludes))
    return results


def import_module_and_get_attrs(
    name: str, *, recursive: bool = True, excludes: typing.List[str] = []
) -> typing.Dict[str, typing.Type[typing.Any]]:
    results: typing.Dict[str, typing.Type[typing.Any]] = {}
    path = '/'.join(list(Path(str(Path(name).absolute()).replace('../', '')).parts[-len(Path(name).parts) :]))
    for name, module in import_submodules(
        path=path[1:] if path.startswith('//') else path,
        recursive=recursive,
        excludes=[Path(exclude) for exclude in excludes if Path(exclude).exists()],
    ).items():
        for _, svc in module.__dict__.items():
            if hasattr(svc, '__module__') and svc.__module__ == name:
                full_name = svc.__module__ + '.' + svc.__name__
                results[full_name] = svc
    return results


def raise_(err: BaseException) -> BaseException:
    raise err  # pragma: no cover


def re_finditer(pattern: typing.Any, string: typing.Any) -> typing.List[typing.Any]:
    return list((finditer(pattern, string) if isinstance(string, str) else {}) or {})


def is_abstract(val: typing.Any) -> bool:
    return hasattr(val, '__mro__') and val.__mro__[1:][0] is ABC
