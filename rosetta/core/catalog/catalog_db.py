import typing

from .catalog_base import CatalogBase, SearchResult


class CatalogDB(CatalogBase):
    """ Represents a catalog stored in a database. """

    # TODO: This probably has fields of conn info, etc.

    def find(self, query: str, limit: typing.Union[int | None] = 1, annotations: dict[str, str] = None) \
            -> list[SearchResult]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.
