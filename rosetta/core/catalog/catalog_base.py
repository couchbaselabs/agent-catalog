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
