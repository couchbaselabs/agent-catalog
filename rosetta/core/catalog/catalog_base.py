import abc
import typing
import pydantic

from ..tool.types.descriptor import ToolDescriptor


class FoundItem(pydantic.BaseModel):
    """ A result item in the results from a CatalogBase.find(). """

    tool_descriptor: ToolDescriptor

    # TODO: A FoundItem might one day also contain additional information --
    # such as to help with any further processing of results (e.g., reranking)
    # and with debugging.

    delta: typing.Any


class CatalogBase(abc.ABC):
    """ An abstract base class for a catalog of ToolDescriptors. """

    @abc.abstractmethod
    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        # TODO: The find() method might likely one day need additional,
        # optional params, perhaps to query on tags, labels, annotations,
        # user credentials (for ACL's), etc.?

        raise NotImplementedError("CatalogBase.find()")

    @abc.abstractmethod
    def diff(self, other, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        """ Compare items from self to items from other (a CatalogMem).

            Returns (items_to_upsert, items_to_delete), where the
            items_to_upsert list holds items originating from the
            other CatalogMem, and the items_to_delete list holds
            items originating from the self CatalogBase.

            The items in the other CatalogMem can be 'bare', in that
            they might not yet have augmentations and/or vector embeddings.

            The repo_commit_id of other items vs self items are compared, and the
            repo object (e.g., a git repo) may be consulted for deeper comparisons.
        """

        raise NotImplementedError("CatalogBase.diff()")

    @abc.abstractmethod
    def update(self, meta, repo_commit_id: str,
               items_to_upsert: list[ToolDescriptor],
               items_to_delete: list[ToolDescriptor]):
        """ Updates self from the items to upsert and delete.
        """

        raise NotImplementedError("CatalogBase.update()")
