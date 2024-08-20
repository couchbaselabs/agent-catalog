import typing
import pathlib
import logging
import abc

from ..secrets import put_secret
from ..catalog.catalog_base import (
    CatalogBase,
    SearchResult
)
from ..annotation import AnnotationPredicate
from .loader import EntryLoader

logger = logging.getLogger(__name__)


class Provider(abc.ABC):
    def __init__(self, catalog: CatalogBase, output: pathlib.Path = None,
                 decorator: typing.Callable[[typing.Callable], typing.Any] = None,
                 refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
                 secrets: typing.Optional[dict[str, str]] = None):
        """
        :param catalog: A handle to the catalog. Entries can either be in memory or in Couchbase.
        :param output: Location to place the generated Python stubs (if desired).
        :param decorator: Function to apply to each search result.
        :param refiner: Refiner (reranker / post processor) to use when retrieving tools.
        :param secrets: Map of identifiers to secret values.

        Below, we give an example of how this class is used.
        >>> import rosetta_core.provider as rp
        >>> import rosetta_core.catalog.catalog_mem as rcm
        >>> import os, pathlib
        >>> my_catalog = rcm.CatalogMem.load(pathlib.Path('.rosetta-catalog') / 'tool-catalog.json')
        >>> my_provider = rp.Provider(
        >>>     catalog=my_catalog,
        >>>     secrets={'CB_PASSWORD': os.getenv('MY_CB_PASSWORD')}
        >>> )
        """
        self.catalog = catalog
        self._tool_cache = dict()
        self._loader = EntryLoader(output=output)

        # Handle our defaults.
        self.decorator = decorator if decorator is not None else lambda s: s
        self.refiner = refiner if refiner is not None else lambda s: s
        if secrets is not None:
            # Note: we only register our secrets at instantiation-time.
            for k, v in secrets.items():
                put_secret(k, v)

    def get_tools_for(self, query: str, annotations: str = None, limit: typing.Union[int | None] = 1) \
            -> list[typing.Any]:
        """
        :param query: A string to search the catalog with.
        :param annotations: An annotation query string in the form of KEY=VALUE (AND|OR KEY=VALUE)*.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        annotation_predicate = AnnotationPredicate(query=annotations)
        results = self.refiner(self.catalog.find(query=query, annotations=annotation_predicate, limit=limit))

        # Load all tools that we have not already cached.
        non_cached_results = [f.entry for f in results if f.entry not in self._tool_cache]
        for record_descriptor, tool in self._loader.load(non_cached_results):
            self._tool_cache[record_descriptor] = tool

        # Return the tools from the cache.
        return [self.decorator(self._tool_cache[x.entry]) for x in results]


