import importlib
import pathlib
import sys


def import_module(source_file: pathlib.Path):
    # TODO (GLENN): We should avoid blindly putting things in our path.
    if str(source_file.parent.absolute()) not in sys.path:
        sys.path.append(str(source_file.parent.absolute()))
    return importlib.reload(importlib.import_module(source_file.stem))
