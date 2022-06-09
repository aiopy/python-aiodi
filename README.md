# Python Dependency Injection library

aiodi is a modern Python Dependency Injection library that allows you to standardize and centralize the way objects are constructed in your application highly inspired on [PHP Symfony's DependencyInjection Component](https://symfony.com/components/DependencyInjection).

Key Features:

* **Native-based**: Implements [*PEP 621*](https://www.python.org/dev/peps/pep-0621/) storing project metadata in *pyproject.toml*.
* **Dual mode**: Setting dependencies using *Python*  and using *configuration files*.
* **Clean**: Wherever you want just use it, *no more decorators and defaults everywhere*.

## Installation

Use the package manager [pip](https://pypi.org/project/aiodi/) to install aiodi.

```bash
pip install aiodi
```

## Documentation

- Visit [aiodi docs](https://aiopy.github.io/python-aiodi/).

## Usage

### with Configuration Files

```toml
# sample/pyproject.toml

[tool.aiodi.variables]
name = "%env(str:APP_NAME, 'sample')%"
version = "%env(int:APP_VERSION, '1')%"
log_level = "%env(APP_LEVEL, 'INFO')%"
debug = "%env(bool:int:APP_DEBUG, '0')%"
text = "Hello World"

[tool.aiodi.services."_defaults"]
project_dir = "../../.."

[tool.aiodi.services."logging.Logger"]
class = "sample.libs.utils.get_simple_logger"
arguments = { name = "%var(name)%", level = "%var(log_level)%" }

[tool.aiodi.services."UserLogger"]
type = "sample.libs.users.infrastructure.in_memory_user_logger.InMemoryUserLogger"
arguments = { commands = "@logging.Logger" }

[tool.aiodi.services."*"]
_defaults = { autoregistration = { resource = "sample/libs/*", exclude = "sample/libs/users/{domain,infrastructure/in_memory_user_logger.py,infrastructure/*command.py}" } }
```

```python
# sample/apps/settings.py

from typing import Optional
from aiodi import Container, ContainerBuilder

def container(filename: str, cwd: Optional[str] = None) -> Container:
    return ContainerBuilder(filenames=[filename], cwd=cwd).load()
```

```python
# sample/apps/cli/main.py

from sample.apps.settings import container
from logging import Logger

def main() -> None:
    di = container(filename='../../pyproject.toml')

    di.get(Logger).info('Just simple call get with the type')
    di.get('UserLogger').logger().info('Just simple call get with the service name')
```

### with Python

```python
from abc import ABC, abstractmethod
from logging import Logger, getLogger, NOTSET, StreamHandler, Formatter
from os import getenv

from aiodi import Container
from typing import Optional, Union

_CONTAINER: Optional[Container] = None


def get_simple_logger(
        name: Optional[str] = None,
        level: Union[str, int] = NOTSET,
        fmt: str = '[%(asctime)s] - %(name)s - %(levelname)s - %(message)s',
) -> Logger:
    logger = getLogger(name)
    logger.setLevel(level)
    handler = StreamHandler()
    handler.setLevel(level)
    formatter = Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class GreetTo(ABC):
    @abstractmethod
    def __call__(self, who: str) -> None:
        pass


class GreetToWithPrint(GreetTo):
    def __call__(self, who: str) -> None:
        print('Hello ' + who)


class GreetToWithLogger(GreetTo):
    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def __call__(self, who: str) -> None:
        self._logger.info('Hello ' + who)


def container() -> Container:
    global _CONTAINER
    if _CONTAINER:
        return _CONTAINER
    di = Container({'env': {
        'name': getenv('APP_NAME', 'aiodi'),
        'log_level': getenv('APP_LEVEL', 'INFO'),
    }})
    di.resolve([
        (
            Logger,
            get_simple_logger,
            {
                'name': di.resolve_parameter(lambda di_: di_.get('env.name', typ=str)),
                'level': di.resolve_parameter(lambda di_: di_.get('env.log_level', typ=str)),
            },
        ),
        (GreetTo, GreetToWithLogger),  # -> (GreetTo, GreetToWithLogger, {})
        GreetToWithPrint,  # -> (GreetToWithPrint, GreetToWithPrint, {})
    ])
    di.set('who', 'World!')
    # ...
    _CONTAINER = di
    return di


def main() -> None:
    di = container()

    di.get(Logger).info('Just simple call get with the type')

    for greet_to in di.get(GreetTo, instance_of=True):
        greet_to(di.get('who'))


if __name__ == '__main__':
    main()

```

## Requirements

- Python >= 3.7

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://github.com/aiopy/python-aiodi/blob/master/LICENSE)
