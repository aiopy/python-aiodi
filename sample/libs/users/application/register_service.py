from sample.libs.users.domain.aggregates import User
from sample.libs.users.domain.properties import UserEmail, UserPassword
from sample.libs.users.domain.repositories import UserRepository


class UserRegisterService:
    __slots__ = '_repository'

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def __call__(self, email: str, password: str) -> None:
        user = User(email=UserEmail(email), password=UserPassword(password))
        self._repository.save(user=user)
