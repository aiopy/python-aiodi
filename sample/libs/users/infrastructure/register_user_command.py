from sample.libs.utils import Command


class RegisterUserCommand(Command):
    email: str
    password: str
