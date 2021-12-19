from logging import Logger


class CreateUserService:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def __call__(self, *args) -> None:
        self._logger.info('From CreateUserService', *args)


class CreateSuperUserService:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def __call__(self, *args) -> None:
        self._logger.info('From CreateSuperUserService', *args)
