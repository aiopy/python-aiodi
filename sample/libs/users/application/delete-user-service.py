from logging import Logger


class DeleteUserService:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def __call__(self, *args) -> None:
        self._logger.info('From DeleteUserService', *args)

