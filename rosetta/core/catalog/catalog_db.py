import typing

from ..tool.types.descriptor import ToolDescriptor
from .catalog_base import CatalogBase, FoundItem


class CatalogDB(CatalogBase):
    """ Represents a catalog stored in a database. """

    # TODO: This probably has fields of conn info, etc.

    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.

    def diff(self, other, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        items_to_upsert, items_to_delete = [], [] # TODO.

        return (items_to_upsert, items_to_delete)

    def update(self, meta, repo_commit_id: str,
               items_to_upsert: list[ToolDescriptor],
               items_to_delete: list[ToolDescriptor]):
        pass # TODO.
