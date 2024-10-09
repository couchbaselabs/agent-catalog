import abc
import pydantic
import typing

from libs.agent_catalog_libs.core.annotation import AnnotationPredicate
from libs.agent_catalog_libs.core.record.descriptor import RecordDescriptor
from libs.agent_catalog_libs.core.version import VersionDescriptor


class SearchResult(pydantic.BaseModel):
    """A result item in the results from a CatalogBase.find()."""

    entry: RecordDescriptor
    delta: float

    # TODO: A FoundItem might one day also contain additional information --
    # such as to help with any further processing of results (e.g., reranking)
    # and with debugging.


# TODO (GLENN): Change this name from find to search
class CatalogBase(abc.ABC):
    """An abstract base class for a catalog of RecordDescriptor's."""

    @abc.abstractmethod
    def find(
        self,
        query: str = None,
        name: str = None,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # TODO: The find() method might likely one day need additional,
        # optional params, perhaps to query on tags, labels, annotations,
        # user credentials (for ACL's), etc.?

        raise NotImplementedError("CatalogBase.find()")

    @property
    @abc.abstractmethod
    def version(self) -> VersionDescriptor:
        pass
