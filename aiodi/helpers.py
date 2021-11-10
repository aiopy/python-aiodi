import typing

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
