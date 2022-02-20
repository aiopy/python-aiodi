from pathlib import Path
from typing import Any, Callable, Dict, MutableMapping, NamedTuple, Tuple, Union

from . import Resolver
from .path import PathData
from .service import ServiceDefaults

InputData = Union[str, Path]
OutputData = Union[MutableMapping[str, Any], Dict[str, Any]]


class LoaderMetadata(NamedTuple):
    path_data: PathData
    decoders: Dict[str, Callable[[InputData], OutputData]]

    def decode(self) -> OutputData:
        for filepath in self.path_data.filepaths:
            if filepath.is_file() and filepath.exists():
                ext = filepath.suffix[1:]
                if ext not in self.decoders:
                    raise NotImplemented('Missing {0} decoder to load dependencies'.format(ext.upper()))  # type: ignore
                data = self.decoders[ext](filepath)

                data.setdefault('variables', {})
                data.setdefault('services', {})

                return data
        raise FileNotFoundError('Missing file to load dependencies')


class LoadData(NamedTuple):
    variables: Dict[str, Any]
    services: Dict[str, Any]
    service_defaults: ServiceDefaults

    @classmethod
    def from_metadata(cls, metadata: LoaderMetadata, data: OutputData) -> 'LoadData':
        path_data = metadata.path_data

        defaults = data['services'].get('_defaults', ServiceDefaults()._asdict())
        project_dir = defaults['project_dir']

        if len(project_dir or '') == 0:
            defaults['project_dir'] = path_data.cwd
        else:
            parts_to_remove = len([part for part in Path(project_dir).parts if part == '..'])
            project_dir = '/'.join(path_data.cwd.parts[:-parts_to_remove])

            if project_dir.startswith('//'):
                project_dir = project_dir[1:]

            defaults['project_dir'] = project_dir

        if '_defaults' in data['services']:
            del data['services']['_defaults']

        return cls(
            variables=data['variables'],
            services=data['services'],
            service_defaults=ServiceDefaults(**defaults),
        )


class LoaderResolver(Resolver[LoaderMetadata, LoadData]):
    def extract_metadata(self, data: Dict[str, Any], extra: Dict[str, Any]) -> LoaderMetadata:  # pylint: disable=W0613
        return LoaderMetadata(
            path_data=data['path_data'],
            decoders=data['decoders'],
        )

    def parse_value(
        self,
        metadata: LoaderMetadata,
        retries: int,  # pylint: disable=W0613
        extra: Dict[str, Any],  # pylint: disable=W0613
    ) -> LoadData:
        return LoadData.from_metadata(metadata=metadata, data=metadata.decode())


def prepare_loader_to_parse(
    resolver: Resolver[Any, Any], items: Dict[str, Any], extra: Dict[str, Any]  # pylint: disable=W0613
) -> Dict[str, Tuple[LoaderMetadata, int]]:
    return {
        'value': (resolver.extract_metadata(data=items, extra=extra), 0),
    }
