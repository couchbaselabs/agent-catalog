import shutil
import tempfile
import typing
import pathlib
import importlib
import logging
import inspect
import abc
import sys

from ..tool.generate import (
    SQLPPCodeGenerator,
    SemanticSearchCodeGenerator,
    HTTPRequestCodeGenerator
)
from ..secrets import put_secret
from ..catalog.catalog_base import (
    CatalogBase,
    SearchResult
)
from ..tool.decorator import ToolMarker
from ..record.descriptor import (
    RecordDescriptor,
    RecordKind
)

logger = logging.getLogger(__name__)


class Provider(abc.ABC):
    def __init__(self, catalog: CatalogBase, output_directory: pathlib.Path = None,
                 func_transform: typing.Callable[[typing.Callable], typing.Any] = None,
                 refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
                 secrets: typing.Optional[dict[str, typing.Callable[[], str]]] = None):
        """
        :param catalog: A handle to the catalog. Entries can either be in memory or in Couchbase.
        :param output_directory: Location to place the generated Python stubs.
        :param func_transform: Function to apply to each search result.
        :param refiner: Refiner (reranker / post processor) to use when retrieving tools.
        :param secrets: Map of identifiers to functions (callbacks) that retrieve secrets.

        >>> import rosetta.core.provider as rp
        >>> import rosetta.core.catalog.catalog_mem as rcm
        >>> import langchain_core.tools, os, pathlib
        >>> my_catalog = rcm.CatalogMem.load(pathlib.Path('.rosetta-catalog') / 'tool-catalog.json')
        >>> my_provider = rp.Provider(
        >>>     catalog=my_catalog,
        >>>     func_transform=langchain_core.tools.StructuredTool.from_function,
        >>>     secrets={'CB_PASSWORD': lambda: os.getenv('MY_CB_PASSWORD')}
        >>> )
        """
        self.catalog = catalog
        self._tool_cache = dict()
        self._modules = dict()

        # Handle our defaults.
        if output_directory is not None:
            self.output_directory = output_directory
        else:
            self.output_directory = pathlib.Path(tempfile.mkdtemp())
        if func_transform is not None:
            self.func_transform = func_transform
        else:
            self.func_transform = lambda s: s
        if refiner is not None:
            self.refiner = refiner
        else:
            self.refiner = lambda s: s
        if secrets is not None:
            # Note: we only register our secrets at instantiation-time.
            for k, v in secrets.items():
                put_secret(k, v)

    def get_tools_for(self, query: str, tags: list[str] = None, limit: typing.Union[int | None] = 1) \
            -> list[typing.Any]:
        """
        :param query: A string to search the catalog with.
        :param tags: A list of tags that must exist with each associated entry.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        results = self.refiner(self.catalog.find(query=query, tags=tags, limit=limit))

        # Load all tools that we have not already cached.
        non_cached_results = [f.entry for f in results if f.entry not in self._tool_cache]
        for record_descriptor, tool in self._load_from_descriptors(non_cached_results):
            self._tool_cache[record_descriptor] = tool

        # Return the tools from the cache.
        return [self.func_transform(self._tool_cache[x.entry]) for x in results]

    def _load_from_descriptors(self, descriptors: list[RecordDescriptor]) \
            -> list[tuple[RecordDescriptor, typing.Callable]]:
        # Group all entries by their 'source'.
        source_groups = dict()
        for result in descriptors:
            if result.source not in source_groups:
                # Note: we assume that each source only contains one type (kind) of tool.
                source_groups[result.source] = {
                    'entries': list(),
                    'kind': result.record_kind
                }
            source_groups[result.source]['entries'].append(result)

        # Now, iterate through each group.
        resultant_tools = list()
        for source, group in source_groups.items():
            entries = group['entries']
            if group['kind'] == RecordKind.PythonFunction:
                for entry in entries:
                    resultant_tools.append((entry, self._load_from_module(entry.source, entry),))
            else:
                match group['kind']:
                    case RecordKind.SQLPPQuery:
                        generator = SQLPPCodeGenerator(record_descriptors=entries).generate
                    case RecordKind.SemanticSearch:
                        generator = SemanticSearchCodeGenerator(record_descriptors=entries).generate
                    case RecordKind.HTTPRequest:
                        generator = HTTPRequestCodeGenerator(record_descriptor=entries).generate
                    case _:
                        raise ValueError('Unexpected tool-kind encountered!')
                output = generator(self.output_directory)
                for i in range(len(entries)):
                    resultant_tools.append((entries[i], self._load_from_module(output[i], entries[i]),))

        return resultant_tools

    def _load_from_module(self, filename: pathlib.Path, entry: RecordDescriptor) -> typing.Callable:
        # TODO (GLENN): We should avoid blindly putting things in our path.
        if not str(filename.parent.absolute()) in sys.path:
            sys.path.append(str(filename.parent.absolute()))
        if filename.stem not in self._modules:
            self._modules[filename.stem] = importlib.import_module(filename.stem)

        # Grab the tool that corresponds to the given entry name.
        for name, tool in inspect.getmembers(self._modules[filename.stem]):
            if not isinstance(tool, ToolMarker):
                continue
            if entry.name == name:
                return tool

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        shutil.rmtree(str(self.output_directory.absolute()))
