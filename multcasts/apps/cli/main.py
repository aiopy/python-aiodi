from pprint import pprint

from sample.apps.settings import container


def main() -> None:
    di = container(filename='../../pyproject.toml')
    pprint(di, indent=4, width=120)