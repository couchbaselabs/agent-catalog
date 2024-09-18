import importlib
import importlib.machinery
import inspect
import logging
import pathlib
import sys
import types
import typing
import uuid

from ..record.descriptor import RecordDescriptor
from ..record.descriptor import RecordKind
from ..tool.decorator import ToolMarker
from ..tool.generate import HTTPRequestCodeGenerator
from ..tool.generate import SemanticSearchCodeGenerator
from ..tool.generate import SQLPPCodeGenerator

logger = logging.getLogger(__name__)


class _ModuleLoader(importlib.abc.Loader):
    """Courtesy of https://stackoverflow.com/a/65034099 with some minor tweaks."""

    def __init__(self):
        self._modules = dict()

    def has_module(self, name: str) -> bool:
        return name in self._modules

    def add_module(self, name: str, content: str):
        self._modules[name] = content

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        if self.has_module(spec.name):
            module = types.ModuleType(spec.name)
            exec(self._modules[spec.name], module.__dict__)
            return module

    def exec_module(self, module):
        pass


class _ModuleFinder(importlib.abc.MetaPathFinder):
    """Courtesy of https://stackoverflow.com/a/65034099 with some minor tweaks."""

    def __init__(self, loader: _ModuleLoader):
        self._loader = loader

    def find_spec(self, fullname, path, target=None) -> importlib.machinery.ModuleSpec:
        if self._loader.has_module(fullname):
            return importlib.machinery.ModuleSpec(fullname, self._loader)


class EntryLoader:
    def __init__(self, output: pathlib.Path = None):
        self.output = output
        self._modules = dict()
        self._loader = _ModuleLoader()
        sys.meta_path.append(_ModuleFinder(self._loader))

    def _load_module_from_filename(self, filename: pathlib.Path):
        # TODO (GLENN): We should avoid blindly putting things in our path.
        if str(filename.parent.absolute()) not in sys.path:
            sys.path.append(str(filename.parent.absolute()))
        if filename.stem not in self._modules:
            logger.debug(f"Loading module {filename.stem}.")
            self._modules[filename.stem] = importlib.import_module(filename.stem)

    def _load_module_from_string(self, module_name: str, module_content: str) -> typing.Callable:
        if module_name not in self._modules:
            logger.debug(f"Loading module {module_name} (dynamically generated).")
            self._loader.add_module(module_name, module_content)
            self._modules[module_name] = importlib.import_module(module_name)

    def _get_tool_from_module(self, module_name: str, entry: RecordDescriptor) -> typing.Callable:
        for name, tool in inspect.getmembers(self._modules[module_name]):
            if not isinstance(tool, ToolMarker):
                continue
            if entry.name == name:
                return tool

    def load(
        self, record_descriptors: list[RecordDescriptor]
    ) -> typing.Iterable[tuple[RecordDescriptor, typing.Callable]]:
        # Group all entries by their 'source'.
        source_groups = dict()
        for result in record_descriptors:
            if result.source not in source_groups:
                # Note: we assume that each source only contains one type (kind) of tool.
                source_groups[result.source] = {"entries": list(), "kind": result.record_kind}
            source_groups[result.source]["entries"].append(result)

        # Now, iterate through each group.
        for source, group in source_groups.items():
            logger.debug(f"Handling entries with source {source}.")
            entries = group["entries"]
            match group["kind"]:
                # For PythonFunction records, we load the source directly (using importlib).
                case RecordKind.PythonFunction:
                    source_file = entries[0].source
                    try:
                        self._load_module_from_filename(source_file)
                    except ModuleNotFoundError:
                        logger.warning(f"Module {source_file} not found. Attempting to use the indexed contents.")
                        self._load_module_from_string(source_file.stem, entries[0].contents)
                    for entry in entries:
                        loaded_entry = self._get_tool_from_module(source_file.stem, entry)
                        yield (
                            entry,
                            loaded_entry,
                        )
                    continue

                # For all other records, we generate the source and load this with a custom importlib loader.
                case RecordKind.SQLPPQuery:
                    generator = SQLPPCodeGenerator(record_descriptors=entries).generate
                case RecordKind.SemanticSearch:
                    generator = SemanticSearchCodeGenerator(record_descriptors=entries).generate
                case RecordKind.HTTPRequest:
                    generator = HTTPRequestCodeGenerator(record_descriptors=entries).generate
                case _:
                    raise ValueError("Unexpected tool-kind encountered!")

            for entry, code in zip(entries, generator()):
                module_id = uuid.uuid4().hex
                self._load_module_from_string(module_id, code)
                loaded_entry = self._get_tool_from_module(module_id, entry)
                yield (
                    entry,
                    loaded_entry,
                )
