import abc
import math
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
    delta: float = pydantic.Field(
        description="The cosine similarity between the query and the entry.",
        # Note: this is a bit imprecise, but we need to account for floating point errors.
        le=1.01,
        ge=-1.01,
    )

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

    @abc.abstractmethod
    def get_all_items(self) -> list[RecordDescriptor]:
        """Returns all the catalog items."""

        raise NotImplementedError("CatalogBase.get_all()")

    @staticmethod
    def cosine_similarity(query: list[float], entry: list[float]) -> float:
        dot_product = sum(q * e for q, e in zip(query, entry))
        query_magnitude = math.sqrt(sum(q**2 for q in query))
        entry_magnitude = math.sqrt(sum(e**2 for e in entry))
        return dot_product / (query_magnitude * entry_magnitude)

    @classmethod
    def get_deltas(cls, query: list[float], entries: list[list[float]]) -> list[float]:
        """Returns the cosine similarity between the query and the entry."""
        return [cls.cosine_similarity(query, entry) for entry in entries]

    @property
    @abc.abstractmethod
    def version(self) -> VersionDescriptor:
        pass
