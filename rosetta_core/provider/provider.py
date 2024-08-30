import abc
import logging
import pathlib
import typing

from ..annotation import AnnotationPredicate
from ..catalog import CatalogBase
from ..catalog import SearchResult
from ..secrets import put_secret
from .loader import EntryLoader

logger = logging.getLogger(__name__)


class BaseProvider(abc.ABC):
    def __init__(
        self,
        catalog: CatalogBase,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
    ):
        self.catalog = catalog
        self.refiner = refiner if refiner is not None else lambda s: s

    @abc.abstractmethod
    def search(self, query: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        pass

    @abc.abstractmethod
    def get(self, name: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        pass


class PromptProvider(BaseProvider):
    def search(self, query: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.refiner(self.catalog.find(query=query, annotations=annotation_predicate, limit=limit))
        return [r.entry.prompt for r in results]

    def get(self, name: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        raise NotImplementedError()


class ToolProvider(BaseProvider):
    def __init__(
        self,
        catalog: CatalogBase,
        output: pathlib.Path = None,
        decorator: typing.Callable[[typing.Callable], typing.Any] = None,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
        secrets: typing.Optional[dict[str, str]] = None,
    ):
        """
        :param catalog: A handle to the catalog. Entries can either be in memory or in Couchbase.
        :param output: Location to place the generated Python stubs (if desired).
        :param decorator: Function to apply to each search result.
        :param refiner: Refiner (reranker / post processor) to use when retrieving tools.
        :param secrets: Map of identifiers to secret values.

        Below, we give an example of how this class is used.
        >>> import rosetta_core.provider as rp
        >>> import rosetta_core.catalog as rcm
        >>> import os, pathlib
        >>> my_catalog = rcm.CatalogMem.load(pathlib.Path('.rosetta-catalog') / 'tool-catalog.json')
        >>> my_provider = rp.ToolProvider(
        >>>     catalog=my_catalog,
        >>>     secrets={'CB_PASSWORD': os.getenv('MY_CB_PASSWORD')}
        >>> )
        """
        super(ToolProvider, self).__init__(catalog=catalog, refiner=refiner)
        self._tool_cache = dict()
        self._loader = EntryLoader(output=output)

        # Handle our defaults.
        self.decorator = decorator if decorator is not None else lambda s: s
        if secrets is not None:
            # Note: we only register our secrets at instantiation-time.
            for k, v in secrets.items():
                put_secret(k, v)

    def search(self, query: str, annotations: str = None, limit: typing.Union[int | None] = 1) -> list[typing.Any]:
        """
        :param query: A string to search the catalog with.
        :param annotations: An annotation query string in the form of KEY=VALUE (AND|OR KEY=VALUE)*.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.refiner(self.catalog.find(query=query, annotations=annotation_predicate, limit=limit))

        # Load all tools that we have not already cached.
        non_cached_results = [f.entry for f in results if f.entry not in self._tool_cache]
        for record_descriptor, tool in self._loader.load(non_cached_results):
            self._tool_cache[record_descriptor] = tool

        # Return the tools from the cache.
        return [self.decorator(self._tool_cache[x.entry]) for x in results]

    def get(self, name: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        raise NotImplementedError()
