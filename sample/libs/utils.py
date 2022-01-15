from abc import ABC
from logging import NOTSET, Formatter, Logger, StreamHandler, getLogger
from typing import Any, Union


def get_simple_logger(
    name: str,
    level: Union[str, int] = NOTSET,
    fmt: str = '[%(asctime)s] - %(name)s - %(levelname)s - %(message)s',
) -> Logger:
    logger = getLogger(name)
    logger.setLevel(level)
    handler = StreamHandler()
    handler.setLevel(level)
    formatter = Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class ValueObject(ABC):
    __slots__ = '_value'

    def __init__(self, value: Any) -> None:
        self._value = value

    def value(self) -> Any:
        return self._value


class Command(ABC):
    pass
