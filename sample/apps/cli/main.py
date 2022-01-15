from pprint import pprint

from sample.apps.settings import container
from sample.libs.users.application.finder_service import UserFinderService
from sample.libs.users.application.register_service import UserRegisterService
from sample.libs.users.domain.properties import UserEmail, UserPassword


def main() -> None:
    di = container()

    # pprint(di, indent=4, width=120)

    email = UserEmail('foo@example.com')

    di.get(UserRegisterService).__call__(email=email, password=UserPassword('secret'))
    di.get(UserFinderService).__call__(email=email)

