from pprint import pprint

from sample.apps.settings import container


def main(filename: str = '../../pyproject.toml') -> None:
    di = container(filename=filename)
    pprint(di, indent=4, width=120)
