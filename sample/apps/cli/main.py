from pprint import pprint

from sample.apps.settings import container


def main() -> None:
    di = container(filename='../../pyproject.toml')
    pprint(di, indent=4, width=120)
    # from logging import Logger
    # di.get(Logger).info('Just simple call get with the type')
    # di.get('UserLogger').logger().info('Just simple call get with the service name')
