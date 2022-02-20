from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, NamedTuple, TypeVar

Metadata = TypeVar('Metadata', bound=NamedTuple)
Value = TypeVar('Value', bound=Any)


class ValueNotFound(Exception):
    __slots__ = ('_key', '_name')

    def __init__(self, kind: str = 'Value', name: str = '?') -> None:
        super().__init__('{0} <{1}> not found!'.format(kind, name))
        self._kind = kind
        self._name = name

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def name(self) -> str:
        return self._name


class ValueResolutionPostponed(Exception, Generic[Metadata]):
    __slots__ = ('_key', '_value', '_times')

    def __init__(self, key: str, value: Metadata, times: int) -> None:
        super().__init__('<{0}> resolution postponed {1} time{2}'.format(key, times, 's' if times > 1 else ''))
        self._key = key
        self._value = value
        self._times = times

    def key(self) -> str:
        return self._key

    def value(self) -> Metadata:
        return self._value

    def times(self) -> int:
        return self._times


class Resolver(ABC, Generic[Metadata, Value]):
    @abstractmethod
    def extract_metadata(self, data: Dict[str, Any], extra: Dict[str, Any]) -> Metadata:
        """
        Extract metadata from data

        :param data: The data to extract the value
        :param extra
        :return: The Metadata from data.
        """

    @abstractmethod
    def parse_value(self, metadata: Metadata, retries: int, extra: Dict[str, Any]) -> Value:
        """
        Parse value from metadata

        :param metadata: Metadata to parse the value
        :param retries: Number of retries. -1 means no retries
        :param extra
        :return: The parsed Value from Metadata
        :raises:
            ValueResolutionPostponed
            ValueNotFound
        """
