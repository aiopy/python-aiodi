from logging import Logger

from sample.libs.users.domain.properties import UserEmail
from sample.libs.users.domain.repositories import UserRepository


class UserFinderService:
    __slots__ = ('_repository', '_logger')

    def __init__(self, repository: UserRepository, logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    def __call__(self, email: str) -> None:
        user = self._repository.find_one(email=UserEmail(email))
        self._logger.info('User <{0}> found!'.format(user.email().value().value()))
