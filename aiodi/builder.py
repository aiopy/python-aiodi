from random import shuffle
from typing import Any, Dict, List, Optional

from .container import Container
from .logger import logger
from .resolver import Resolver, ValueResolutionPostponed
from .resolver.loader import LoadData, LoaderResolver
from .resolver.path import PathData, PathResolver
from .resolver.service import (
    ServiceDefaults,
    ServiceResolver,
    prepare_services_to_parse,
)
from .resolver.variable import VariableResolver, prepare_variables_to_parse
from .toml import TOMLDecoder, lazy_toml_decoder


class ContainerBuilder:
    _debug: bool
    _resolvers: Dict[str, Resolver[Any, Any]]
    _decoders: Dict[str, TOMLDecoder]
    _variables_key: str
    _services_key: str
    _path_data: PathData
    _service_defaults: ServiceDefaults
    _items: Dict[str, Dict[str, Any]]

    def __init__(
        self,
        filenames: List[str] = [
            './pyproject.toml',
            './services.toml',
            './../pyproject.toml',
            './../services.toml',
        ],
        cwd: Optional[str] = None,
        *,
        debug: bool = False,
        tool_key: str = 'aiodi',
        var_key: str = 'env',  # Container retro-compatibility
        toml_decoder: Optional[TOMLDecoder] = None
    ) -> None:
        self._debug = debug

        self._variables_key = str('env' if var_key is None or len(var_key) == 0 else var_key)
        self._services_key = 'services'

        self._resolvers = {
            'loader': LoaderResolver(),
            'path': PathResolver(),
            'service': ServiceResolver(),
            'variable': VariableResolver(),
        }
        self._decoders = {
            'toml': lambda path: (toml_decoder or lazy_toml_decoder())(path).get('tool', {}).get(tool_key, {}),
        }

        self._path_data = self._resolvers['path'].parse_value(
            metadata=self._resolvers['path'].extract_metadata(data={'cwd': cwd, 'filenames': filenames})
        )

        self._service_defaults = ServiceDefaults()
        self._items = {
            self._variables_key: {},
            self._services_key: {},
        }

    def load(self) -> Container:
        data: LoadData = self._resolvers['loader'].parse_value(
            metadata=self._resolvers['loader'].extract_metadata(
                data={
                    'service_defaults': self._service_defaults,
                    'path_data': self._path_data,
                    'decoders': self._decoders,
                }
            )
        )

        self._service_defaults = data.service_defaults
        self._path_data = data.path_data

        extra = {
            '_service_defaults': self._service_defaults,
            'variables': self._items[self._variables_key],
            'services': self._items[self._services_key],
            'resolvers': self._resolvers,
        }

        self._parse_values(
            resolver_=self._resolvers['variable'],
            storage=self._items[self._variables_key],
            extra=extra,
            items=prepare_variables_to_parse(resolver=self._resolvers['variable'], items=data.variables, extra=extra),
        )
        self._parse_values(
            resolver_=self._resolvers['service'],
            storage=self._items[self._services_key],
            extra=extra,
            items=prepare_services_to_parse(resolver=self._resolvers['service'], items=data.services, extra=extra),
        )

        return Container(items=[(key, val, {}) for key, val in self._items.items()])

    def _parse_values(
        self,
        resolver_: Resolver[Any, Any],
        storage: Dict[str, Any],
        extra: Dict[str, Any],
        items: Dict[str, Any],
    ) -> None:
        limit_retries = pow(len(items.keys()), 3)
        while len(items.keys()) > 0:
            try:
                for name, (metadata, times) in items.items():
                    storage.setdefault(name, resolver_.parse_value(metadata=metadata, retries=times, extra=extra))
            except ValueResolutionPostponed as err:
                if self._debug:
                    logger.debug(err.__str__())
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
