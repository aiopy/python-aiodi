from pathlib import Path
from typing import Any, Callable, MutableMapping, cast

TOMLDecoded = MutableMapping[str, Any] | dict[str, Any]
TOMLPath = str | Path
TOMLDecoder = Callable[[TOMLPath], TOMLDecoded]


def _decoder_from_builtin_lib() -> TOMLDecoder:
    from tomllib import load

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'rb') as file:
            return cast(TOMLDecoded, load(file))

    return decorator


def _decoder_from_pytomlpp_lib() -> TOMLDecoder:
    from pytomlpp import load

    return load  # type: ignore


def _decoder_from_rtoml_lib() -> TOMLDecoder:
    from rtoml import load

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'r', encoding='utf-8') as file:
            return load(file)  # type: ignore

    return decorator


def _decoder_from_tomli_lib() -> TOMLDecoder:
    from tomli import load

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'rb') as file:
            return cast(TOMLDecoded, load(file))

    return decorator


def _decoder_from_pytoml_lib() -> TOMLDecoder:
    from pytoml import load

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'rb') as file:
            return load(file)  # type: ignore

    return decorator


def _decoder_from_toml_lib() -> TOMLDecoder:
    from toml import load

    return load


def _decoder_from_qtoml_lib() -> TOMLDecoder:
    from qtoml import load

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'r', encoding='utf-8') as file:
            return load(file)  # type: ignore

    return decorator


def _decoder_from_tomlkit_lib() -> TOMLDecoder:
    from tomlkit import parse

    def decorator(path: TOMLPath) -> TOMLDecoded:
        with open(path, 'r', encoding='utf-8') as file:
            return parse(file.read())

    return decorator


_decoders = [
    _decoder_from_builtin_lib,
    _decoder_from_pytomlpp_lib,
    _decoder_from_rtoml_lib,
    _decoder_from_tomli_lib,
    _decoder_from_pytoml_lib,
    _decoder_from_toml_lib,
    _decoder_from_qtoml_lib,
    _decoder_from_tomlkit_lib,
]


def lazy_toml_decoder() -> TOMLDecoder:
    for decoder in _decoders:
        try:
            return decoder()
        except (ModuleNotFoundError, ImportError):
            continue
    raise RuntimeError('Missing TOML decoder library to use aiodi')
