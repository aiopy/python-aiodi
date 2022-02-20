from logging import Logger
from pathlib import Path

import pytest

from sample.apps.settings import container
from sample.libs.users.application.finder_service import UserFinderService
from sample.libs.users.application.register_service import UserRegisterService
from sample.libs.users.domain.repositories import UserRepository
from sample.libs.users.infrastructure.in_memory_user_logger import InMemoryUserLogger
from sample.libs.users.infrastructure.in_memory_user_repository import (
    InMemoryUserRepository,
)


@pytest.mark.timeout(15)
def test_container() -> None:
    di = container(filename='../../../sample/pyproject.toml', cwd=str(Path(__file__).parent.absolute()))

    assert 'env.log_level' in di and di.get('env.log_level', typ=str) == 'INFO'
    assert 'env.name' in di and di.get('env.name', typ=str) == 'sample'
    assert 'env.version' in di and di.get('env.version', typ=int) == 1
    assert 'env.debug' in di and di.get('env.debug', typ=bool) is False
    assert 'env.text' in di and di.get('env.text', typ=str) == 'Hello World'

    assert 'UserLogger' in di and di.get('UserLogger', typ=InMemoryUserLogger)
    assert 'logging.Logger' in di and di.get(Logger)

    assert 'sample.libs.users.application.finder_service.UserFinderService' in di and di.get(UserFinderService)
    assert 'sample.libs.users.application.register_service.UserRegisterService' in di and di.get(UserRegisterService)
    assert 'sample.libs.users.infrastructure.in_memory_user_repository.InMemoryUserRepository' in di and isinstance(
        di.get(InMemoryUserRepository), UserRepository
    )

    assert 'UserRepository' not in di  # just to ensure arg to be resolved is taken per fqdn instead of name
