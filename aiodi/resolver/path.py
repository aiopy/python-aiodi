from os.path import abspath, dirname
from pathlib import Path
from sys import executable, modules
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from . import Resolver


class PathMetadata(NamedTuple):
    cwd: Optional[str]
    filenames: List[str]

    def compute_cwd(self) -> Path:
        if self.cwd:
            return Path(self.cwd)
        try:
            main_file = abspath(modules['__main__'].__file__)  # type: ignore
        except Exception:
            main_file = executable
        return Path(dirname(main_file))  # type: ignore

    def compute_filepaths(self, cwd: Path) -> List[Path]:
        filepaths: List[Path] = []
        for filename in self.filenames:
            parts_to_remove = len(([part for part in Path(filename).parts if part == '..']))
            filename_ = '/'.join(
                [
                    *(cwd.parts if parts_to_remove == 0 else cwd.parts[:-parts_to_remove]),
                    *Path(filename).parts[parts_to_remove:],
                ]
            )
            if filename_.startswith('//'):
                filename_ = filename_[1:]
            filepaths.append(Path(filename_))
        return filepaths


class PathData(NamedTuple):
    cwd: Path
    filepaths: List[Path]

    @classmethod
    def from_metadata(cls, metadata: PathMetadata) -> 'PathData':
        cwd = metadata.compute_cwd()
        filepaths = metadata.compute_filepaths(cwd=cwd)
        return cls(cwd=cwd, filepaths=filepaths)


class PathResolver(Resolver[PathMetadata, PathData]):
    def extract_metadata(self, data: Dict[str, Any], extra: Dict[str, Any]) -> PathMetadata:  # pylint: disable=W0613
        return PathMetadata(cwd=data.get('cwd', None), filenames=data.get('filenames', []))

    def parse_value(
        self,
        metadata: PathMetadata,
        retries: int,  # pylint: disable=W0613
        extra: Dict[str, Any],  # pylint: disable=W0613
    ) -> PathData:
        return PathData.from_metadata(metadata)


def prepare_path_to_parse(
    resolver: Resolver[Any, Any], items: Dict[str, Any], extra: Dict[str, Any]  # pylint: disable=W0613
) -> Dict[str, Tuple[PathMetadata, int]]:
    return {
        'value': (resolver.extract_metadata(data=items, extra=extra), 0),
    }
