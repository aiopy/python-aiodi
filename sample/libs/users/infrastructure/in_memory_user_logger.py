from logging import Logger


class InMemoryUserLogger:
    __slots__ = '_logger'

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def logger(self) -> Logger:
        return self._logger
