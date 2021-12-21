from pprint import pprint

from aiodi.builder import ContainerBuilder


def main() -> None:
    container = ContainerBuilder(filenames=['../pyproject.toml'], debug=True).load()
    pprint(container, indent=4, width=120)


if __name__ == '__main__':
    main()
