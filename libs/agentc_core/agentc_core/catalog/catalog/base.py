import abc
import pydantic
import typing

from ...annotation import AnnotationPredicate
from ...record.descriptor import RecordDescriptor
from ...version import VersionDescriptor

# Constant to represent the latest snapshot version.
LATEST_SNAPSHOT_VERSION = "__LATEST__"


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
        snapshot: str = None,
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
