from typing import List, Optional

from sample.libs.users.domain.aggregates import User
from sample.libs.users.domain.errors import UserNotFound
from sample.libs.users.domain.properties import UserEmail
from sample.libs.users.domain.repositories import UserRepository


class InMemoryUserRepository(UserRepository):
    _users: List[User]

    def __init__(self) -> None:
        self._users = []

    def save(self, user: User) -> None:
        found: bool = False
        for user_ in self._users:
            if user_.email().value() == user.email().value():
                found = True
                break
        if not found:
            self._users.append(user)

    def find_one(self, email: UserEmail) -> User:
        user: Optional[User] = None
        for user_ in self._users:
            if user_.email().value() == email.value():
                user = user_
                break
        if not user:
            raise UserNotFound()
        return user
