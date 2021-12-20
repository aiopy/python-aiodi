from abc import ABC
from logging import Logger


class GreetTo(ABC):
    def __call__(self, who: str) -> None:
        pass


class GreetToWithPrint(GreetTo):
    def __call__(self, who: str) -> None:
        print('Hello ' + who)


class GreetToWithLogger(GreetTo):
    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def __call__(self, who: str) -> None:
        self._logger.info('Hello ' + who)


def fake_log() -> GreetTo:
    return GreetToWithLogger(Logger('Baaaa'))
