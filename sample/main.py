from logging import Logger
from pprint import pprint

from aiodi.builder import ContainerBuilder
from sample.blabla.log import GreetToWithLogger


def main() -> None:
    container = ContainerBuilder(debug=True).load()
    print()
    print()
    pprint(container)
    print('version es: ', container.get('env.version'))
    print('version es: ', type(container.get('env.version')))
    container.get(Logger).info('Hello World!')
    container.get(GreetToWithLogger).__call__('aiodi')


if __name__ == '__main__':
    main()
