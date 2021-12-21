from abc import ABC
from logging import Logger


class PelotaInfra:
    def __init__(self, svc: Logger) -> None:
        self._svc = svc


class PelotaAbsoluta(ABC):
    pass
