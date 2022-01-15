from aiodi import Container, ContainerBuilder


def container(filename: str) -> Container:
    return ContainerBuilder(filenames=[filename]).load()
