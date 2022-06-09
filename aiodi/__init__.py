"""Container for the Dependency Injection in Python."""
# pylint: skip-file
from .builder import ContainerBuilder
from .container import Container, ContainerKey

__version__ = '1.1.4'

__all__ = (
    # di
    'Container',
    'ContainerKey',
    'ContainerBuilder',
)
