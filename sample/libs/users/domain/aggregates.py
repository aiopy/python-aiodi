from sample.libs.users.domain.properties import UserEmail, UserPassword


class User:
    _email: UserEmail
    _password: UserPassword

    def __init__(self, email: UserEmail, password: UserPassword) -> None:
        self._email = email
        self._password = password

    def email(self) -> UserEmail:
        return self._email
