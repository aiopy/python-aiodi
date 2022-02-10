from os import getenv
from typing import Any, Dict, List, Match, NamedTuple, Tuple, Type

from ..helpers import raise_, re_finditer
from . import Resolver, ValueNotFound, ValueResolutionPostponed

REGEX = r"%(static|env|var)\((str:|int:|float:|bool:)?([\w]+)(,\s{1}'.*?')?\)%"
STATIC_TEMPLATE: str = "%static({0}:{1}, '{2}')%"


class VariableMetadata(NamedTuple):
    name: str
    value: Any
    matches: List['VariableMetadata.MatchMetadata'] = []  # type: ignore

    class MatchMetadata(NamedTuple):  # type: ignore
        source_kind: str
        type: Type[Any]
        source_name: str
        default: Any
        match: Match

        @classmethod
        def from_match(cls, match: Match) -> 'VariableMetadata.MatchMetadata':
            return cls(
                source_kind=str(match.groups()[0]),
                type=str if match.groups()[1] is None else globals()['__builtins__'][str(match.groups()[1])[:-1]],
                source_name=str(match.groups()[2]),
                default=None if match.groups()[3] is None else str(match.groups()[3])[3:-1],
                match=match,
            )


class VariableNotFound(ValueNotFound):
    def __init__(self, name: str) -> None:
        super().__init__(kind='Variable', name=name)


class VariableResolutionPostponed(ValueResolutionPostponed[VariableMetadata]):
    pass


class VariableResolver(Resolver[VariableMetadata, Any]):
    @staticmethod
    def _metadata_matches(key: str, val: Any) -> List[Match]:
        def __call__(string: Any) -> List[Match]:
            return re_finditer(pattern=REGEX, string=string)

        return __call__(string=val) or __call__(string=STATIC_TEMPLATE.format(type(val).__name__, key, val))

    def extract_metadata(
        self, data: Dict[str, Any], extra: Dict[str, Any] = {}  # pylint: disable=W0613
    ) -> VariableMetadata:
        key: str = data.get('key') or raise_(KeyError('Missing key "key" to extract variable metadata'))  # type: ignore
        val: Any = data.get('val') or raise_(KeyError('Missing key "val" to extract variable metadata'))

        return VariableMetadata(
            name=key,
            value=val,
            matches=[
                VariableMetadata.MatchMetadata.from_match(match=match)
                for match in self._metadata_matches(key=key, val=val)
            ],
        )

    def parse_value(
        self, metadata: VariableMetadata, retries: int = -1, extra: Dict[str, Any] = {}  # pylint: disable=W0613
    ) -> Any:
        _variables: Dict[str, Any] = extra.get('variables')  # type: ignore
        if _variables is None:
            raise KeyError('Missing key "variables" to parse variable value')

        values: List[str] = []
        for idx, metadata_ in enumerate(metadata.matches):
            typ_val: str = ''
            if metadata_.source_kind == 'static':
                typ_val = metadata_.default
            elif metadata_.source_kind == 'env':
                typ_val = getenv(key=metadata_.source_name, default=metadata_.default or '')
            elif metadata_.source_kind == 'var':
                if metadata_.source_name not in _variables:
                    if retries != -1:
                        raise VariableResolutionPostponed(key=metadata.name, value=metadata, times=retries + 1)
                    raise VariableNotFound(name=metadata.name)
                typ_val = _variables.get(metadata_.source_name, metadata_.default)
            # concatenate right side content per iteration
            values += (
                metadata.value[0 if idx == 0 else metadata.matches[idx - 1].match.end() : metadata_.match.start()]
                + typ_val
            )
            # concatenate static content in last iteration
            if (len(metadata) - 1) == idx:
                values += metadata.value[metadata_.match.end() :]
        value: Any = ''.join(values)
        if len(metadata.matches) == 1:
            value = metadata.matches[0].type(value)
        return value


def prepare_variables_to_parse(
    resolver: Resolver[Any, Any], items: Dict[str, Any], extra: Dict[str, Any]  # pylint: disable=W0613
) -> Dict[str, Tuple[VariableMetadata, int]]:
    return dict([(key, (resolver.extract_metadata(data={'key': key, 'val': val}), 0)) for key, val in items.items()])
