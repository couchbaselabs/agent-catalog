from .catalog_base import CatalogBase, FoundItem


class CatalogDB(CatalogBase):
    """ Represents a catalog stored in a database. """

    # TODO: This probably has fields of conn info, etc.

    def find(self, query: str, max: int = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.
