import abc
import json
import pathlib
import typing

from ..tool.types.descriptor import ToolDescriptor

from .descriptor import CatalogDescriptor


class CatalogRef(abc.ABC):
    """ An abstract interface for a catalog reference. """

    @abc.abstractmethod
    def find(self, todo):
        """ Returns the ToolDescriptors from the catalog that best match a query. """
        pass


class MemCatalogRef(CatalogRef):
    """ Represents an in-memory catalog ref. """

    catalog_path: pathlib.Path

    catalog_descriptor: CatalogDescriptor

    def load(self):
        with self.catalog_path.open('r') as fp:
            self.catalog_descriptor = json.load(fp)

    def find(self, todo) -> list[ToolDescriptor]:
        """ Returns the ToolDescriptors that best match a query. """
        pass # TODO.

    def updateFrom(self, source: typing.Self, repo):
        # TODO.
        pass


class DBCatalogRef(CatalogRef):
    """ Represents a catalog stored in a database. """

    def find(self, todo) -> list[ToolDescriptor]:
        """ Returns the ToolDescriptors that best match a query. """
        pass # TODO: SQL++ and vector index searches likely are involved here.

    def updateFrom(self, source: MemCatalogRef, repo):
        # TODO.
        pass


class ChainedCatalogRef(CatalogRef):
    """ Represents a chain of catalogs, where items from
        earlier catalogs take precendence. """

    children: list[CatalogRef]

    def find(self, todo) -> list[ToolDescriptor]:
        # TODO: This might roughly look something like...

        results = []

        for c in self.children:
            results_c = c.find(todo)

            # TODO: Filter out entries from results_c which
            # are shadowed by the entries in the existing results.

            results += results_c

        return results
