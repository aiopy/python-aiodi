from typing import Optional

from aiodi import Container, ContainerBuilder


def container(filename: str, cwd: Optional[str] = None) -> Container:
    return ContainerBuilder(filenames=[filename], cwd=cwd).load()
