from abc import ABC, abstractmethod

from sample.libs.users.domain.aggregates import User
from sample.libs.users.domain.properties import UserEmail


class UserRepository(ABC):
    @abstractmethod
    def save(self, user: User) -> None:
        pass

    @abstractmethod
    def find_one(self, email: UserEmail) -> User:
        pass
