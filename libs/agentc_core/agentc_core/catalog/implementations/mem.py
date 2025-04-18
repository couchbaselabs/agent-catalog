import click_extra
import logging
import pathlib
import pydantic
import typing

from ...annotation import AnnotationPredicate
from ...catalog.descriptor import CatalogDescriptor
from ...config import LATEST_SNAPSHOT_VERSION
from ...learned.embedding import EmbeddingModel
from ...version import VersionDescriptor
from .base import CatalogBase
from .base import SearchResult
from agentc_core.record.descriptor import RecordDescriptor

logger = logging.getLogger(__name__)


class CatalogMem(pydantic.BaseModel, CatalogBase):
    """Represents an in-memory catalog."""

    embedding_model: EmbeddingModel
    catalog_file: typing.Optional[pathlib.Path] = None
    catalog_descriptor: typing.Optional[CatalogDescriptor] = None

    @pydantic.model_validator(mode="after")
    def _catalog_path_or_descriptor_should_exist(self) -> "CatalogMem":
        if self.catalog_descriptor is not None:
            return self

        if self.catalog_file is None:
            raise ValueError("CatalogMem must be initialized with a catalog path or a descriptor.")
        elif not self.catalog_file.exists():
            raise ValueError(f"Catalog path '{self.catalog_file}' does not exist.")

        # If there are any validation errors in the local catalog, we'll catch them here.
        with self.catalog_file.open("r") as fp:
            self.catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())

        return self

    def dump(self, catalog_path: pathlib.Path):
        """Save to a catalog_path JSON file."""
        self.catalog_descriptor.items.sort(key=lambda x: x.identifier)
        with catalog_path.open("w") as fp:
            fp.write(str(self.catalog_descriptor))
            fp.write("\n")

    def find(
        self,
        query: str = None,
        name: str = None,
        snapshot: str = None,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""
        if snapshot != LATEST_SNAPSHOT_VERSION:
            # We cannot return anything other than the latest snapshot.
            logger.debug("Specific snapshot has been specified. Returning empty list (for in-memory catalog).")
            return []

        # Return the exact tool instead of doing vector search in case name is provided
        if name is not None:
            catalog = [x for x in self.catalog_descriptor.items if x.name == name]
            if len(catalog) != 0:
                return [SearchResult(entry=catalog[0], delta=1)]
            else:
                click_extra.secho(f"No catalog items found with name '{name}'", fg="yellow")
                return []

        # If annotations have been specified, prune all tools that do not possess these annotations.
        candidate_tools = [x for x in self.catalog_descriptor.items]
        if annotations is not None:
            candidates_for_annotation_search = candidate_tools.copy()
            candidate_tools = list()
            for tool in candidates_for_annotation_search:
                if tool.annotations is None:
                    # Tools without annotations will always be excluded.
                    continue

                # Iterate through our disjuncts.
                for disjunct in annotations.disjuncts:
                    is_valid_tool = True
                    for k, v in disjunct.items():
                        if k not in tool.annotations or tool.annotations[k] != v:
                            is_valid_tool = False
                            break
                    if is_valid_tool:
                        candidate_tools += [tool]
                        break

        if len(candidate_tools) == 0:
            # Exit early if there are no candidates.
            return list()

        # Compute the distance of each tool in the catalog to the query.
        deltas = self.get_deltas(
            query=self.embedding_model.encode(query), entries=[t.embedding for t in candidate_tools]
        )

        # Order results by their distance to the query (larger is "closer").
        results = [SearchResult(entry=candidate_tools[i], delta=deltas[i]) for i in range(len(deltas))]
        results = sorted(results, key=lambda t: t.delta, reverse=True)

        # Apply our limit clause.
        if limit > 0:
            results = results[:limit]
        return results

    def __iter__(self) -> list[RecordDescriptor]:
        yield from self.catalog_descriptor.items

    @property
    def version(self) -> VersionDescriptor:
        return self.catalog_descriptor.version
