from aiodi import Container, ContainerBuilder


def container() -> Container:
    return ContainerBuilder(filenames=['../../pyproject.toml']).load()
