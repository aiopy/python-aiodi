from pathlib import Path
from typing import Any, Callable, Dict, MutableMapping, NamedTuple, Union

from . import Resolver
from .path import PathData
from .service import ServiceDefaults

InputData = Union[str, Path]
OutputData = Union[MutableMapping[str, Any], Dict[str, Any]]


class LoaderMetadata(NamedTuple):
    service_defaults: ServiceDefaults
    path_data: PathData
    decoders: Dict[str, Callable[[InputData], OutputData]]

    def decode(self) -> OutputData:
        for filepath in self.path_data.filepaths:
            if filepath.is_file() and filepath.exists():
                fmt = filepath.suffix[1:]
                if fmt not in self.decoders:
                    raise NotImplemented('Missing {0} decoder to load dependencies'.format(fmt.upper()))
                data = self.decoders[fmt](filepath)

                data.setdefault('variables', {})
                data.setdefault('services', {})

                data.get('services').setdefault('_defaults', self.service_defaults._asdict())

                return data
        raise FileNotFoundError('Missing file to load dependencies')


class LoadData(NamedTuple):
    variables: Dict[str, Any]
    services: Dict[str, Any]
    service_defaults: ServiceDefaults
    path_data: PathData

    @classmethod
    def from_metadata(cls, metadata: LoaderMetadata, data: OutputData) -> 'LoadData':
        path_data = metadata.path_data
        defaults = data.get('services').get('_defaults')
        project_dir = defaults.get('project_dir')

        if project_dir is None or len(project_dir) == 0:
            defaults['project_dir'] = path_data.cwd
        else:
            parts_to_remove = len([part for part in Path(project_dir).parts if part == '..'])
            project_dir = '/'.join(path_data.cwd.parts[:-parts_to_remove])

            if project_dir.startswith('//'):
                project_dir = project_dir[1:]

            defaults['project_dir'] = project_dir
            path_data = PathData(cwd=Path(project_dir), filepaths=path_data.filepaths)

        if '_defaults' in data.get('services'):
            del data.get('services')['_defaults']

        return cls(
            variables=data.get('variables'),
            services=data.get('services'),
            service_defaults=ServiceDefaults(**defaults),
            path_data=path_data,
        )


class LoaderResolver(Resolver[LoaderMetadata, LoadData]):
    def extract_metadata(self, data: Dict[str, Any], extra: Dict[str, Any] = {}) -> LoaderMetadata:
        return LoaderMetadata(
            service_defaults=data.get('service_defaults'),
            path_data=data.get('path_data'),
            decoders=data.get('decoders'),
        )

    def parse_value(self, metadata: LoaderMetadata, retries: int = -1, extra: Dict[str, Any] = {}) -> LoadData:
        return LoadData.from_metadata(metadata=metadata, data=metadata.decode())
