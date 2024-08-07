import abc
import json
import pathlib
import typing
import pydantic

from ..tool.types.descriptor import ToolDescriptor

from .descriptor import CatalogDescriptor


class FoundItem(pydantic.BaseModel):
    """ A result item in the results from a CatalogRef.find(). """

    tool_descriptor: ToolDescriptor

    # TODO: A FoundItem might one day also contain a similarity score
    # or other information -- such as to help with any further
    # processing of results (e.g., reranking)?


class CatalogRef(abc.ABC):
    """ An abstract interface for a catalog reference. """

    @abc.abstractmethod
    def find(self, query) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        # TODO: The find() method might likely one day need additional,
        # optional params, perhaps to query on tags, labels, annotations,
        # user credentials (for ACL's), etc.?

        pass


class MemCatalogRef(CatalogRef):
    """ Represents an in-memory catalog ref. """

    catalog_path: pathlib.Path

    catalog_descriptor: CatalogDescriptor

    def load(self, catalog_path: pathlib.Path) -> typing.Self:
        self.catalog_path = catalog_path

        with self.catalog_path.open('r') as fp:
            self.catalog_descriptor = json.load(fp)

        return self

    def find(self, query) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO.

    def updateFrom(self, source: typing.Self, repo):
        pass # TODO.


class DBCatalogRef(CatalogRef):
    """ Represents a catalog stored in a database. """

    def find(self, query) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.

    def updateFrom(self, source: MemCatalogRef, repo):
        pass # TODO.


class ChainedCatalogRef(CatalogRef):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    children: list[CatalogRef]

    def __init__(self, children):
        self.children = children

    def find(self, query) -> list[ToolDescriptor]:
        # TODO: This might roughly look something like...

        results = []

        for c in self.children:
            results_c = c.find(query)

            # TODO: Filter out entries from results_c which
            # are shadowed by the entries in the existing results.

            results += results_c

        return results
