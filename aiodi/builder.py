from pathlib import Path
from random import shuffle
from typing import Any, Callable, MutableMapping

from .container import Container
from .logger import logger
from .resolver import Resolver, ValueResolutionPostponed
from .resolver.loader import LoadData, LoaderResolver, prepare_loader_to_parse
from .resolver.path import PathResolver, prepare_path_to_parse
from .resolver.service import (
    ServiceDefaults,
    ServiceResolver,
    prepare_services_to_parse,
)
from .resolver.variable import VariableResolver, prepare_variables_to_parse
from .toml import TOMLDecoder, lazy_toml_decoder


class ContainerBuilder:
    _filenames: list[str]
    _cwd: str | None
    _debug: bool
    _resolvers: dict[str, Resolver[Any, Any]]
    _decoders: dict[str, Callable[[str | Path], MutableMapping[str, Any] | dict[str, Any]]]
    _map_items: Callable[[dict[str, dict[str, Any]]], list[tuple[str, Any, dict[str, Any]]]]

    def __init__(
        self,
        filenames: list[str] | None = None,
        cwd: str | None = None,
        *,
        debug: bool = False,
        tool_key: str = 'aiodi',
        var_key: str = 'env',  # Container retro-compatibility
        toml_decoder: TOMLDecoder | None = None,
    ) -> None:
        self._filenames = (
            [
                './pyproject.toml',
                './services.toml',
                './aiodi.toml',
                './../pyproject.toml',
                './../services.toml',
                './../aiodi.toml',
            ]
            if filenames is None or len(filenames) == 0
            else filenames
        )
        self._cwd = None if len(cwd or '') == 0 else cwd
        self._debug = debug
        self._resolvers = {
            'loader': LoaderResolver(),
            'path': PathResolver(),
            'service': ServiceResolver(),
            'variable': VariableResolver(),
        }
        self._decoders = {
            'toml': lambda path: (toml_decoder or lazy_toml_decoder())(path).get('tool', {}).get(tool_key, {}),
        }

        def map_items(items: dict[str, dict[str, Any]]) -> list[tuple[str, Any, dict[str, Any]]]:
            return [
                (key, val, {})
                for key, val in {
                    str('env' if var_key is None or len(var_key) == 0 else var_key): items['variables'],
                    **items['services'],
                }.items()
            ]

        self._map_items = map_items

    def load(self) -> Container:
        extra: dict[str, Any] = {
            'path_data': {},
            'data': {},
            '_service_defaults': ServiceDefaults(),
            'resolvers': self._resolvers,
            'variables': {},
            'services': {},
        }

        self._parse_values(
            resolver=self._resolvers['path'],
            storage=extra['path_data'],
            extra=extra,
            items=prepare_path_to_parse(
                resolver=self._resolvers['path'], items={'cwd': self._cwd, 'filenames': self._filenames}, extra=extra
            ),
        )
        extra['path_data'] = extra['path_data']['value']

        self._parse_values(
            resolver=self._resolvers['loader'],
            storage=extra['data'],
            extra=extra,
            items=prepare_loader_to_parse(
                resolver=self._resolvers['loader'],
                items={'path_data': extra['path_data'], 'decoders': self._decoders},
                extra=extra,
            ),
        )
        data: LoadData = extra['data']['value']
        extra['data'] = data

        extra['_service_defaults'] = data.service_defaults

        self._parse_values(
            resolver=self._resolvers['variable'],
            storage=extra['variables'],
            extra=extra,
            items=prepare_variables_to_parse(resolver=self._resolvers['variable'], items=data.variables, extra=extra),
        )

        self._parse_values(
            resolver=self._resolvers['service'],
            storage=extra['services'],
            extra=extra,
            items=prepare_services_to_parse(resolver=self._resolvers['service'], items=data.services, extra=extra),
        )

        return Container(
            items=self._map_items({'variables': extra['variables'], 'services': extra['services']})  # type: ignore
        )

    def _parse_values(
        self,
        resolver: Resolver[Any, Any],
        storage: dict[str, Any],
        extra: dict[str, Any],
        items: dict[str, Any],
    ) -> None:
        limit_retries = pow(len(items.keys()), 3)
        while len(items.keys()) > 0:
            try:
                for name, (metadata, times) in items.items():
                    storage.setdefault(name, resolver.parse_value(metadata=metadata, retries=times, extra=extra))
            except ValueResolutionPostponed as err:
                if self._debug:
                    logger.debug(str(err))
                if err.times() == limit_retries:
                    raise InterruptedError('Reached limit of retries ({0}) per <{1}>!'.format(limit_retries, err.key()))
                if err.key() not in items:
                    items_list = list({**items, err.key(): (err.value(), err.times())}.items())
                else:
                    items_list = list(items.items())
                shuffle(items_list)  # avoid re-processing same dependency
                items = dict(items_list)
            finally:
                for key in storage.keys():
                    if key in items.keys():
                        del items[key]
