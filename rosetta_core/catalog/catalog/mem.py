import click
import logging
import pathlib
import pydantic
import typing

from .base import CatalogBase
from .base import SearchResult
from rosetta_core.annotation import AnnotationPredicate
from rosetta_core.catalog.descriptor import CatalogDescriptor
from rosetta_core.record.descriptor import RecordDescriptor

logger = logging.getLogger(__name__)


class CatalogMem(pydantic.BaseModel, CatalogBase):
    """Represents an in-memory catalog."""

    catalog_descriptor: CatalogDescriptor = None

    def init_from(self, other: "CatalogMem") -> list[RecordDescriptor]:
        """Initialize the items in self by copying over attributes from
        items found in other that have the exact same versions.

        Returns a list of uninitialized items."""

        uninitialized_items = []
        if other and other.catalog_descriptor:
            # A lookup dict of items keyed by "source:name".
            other_items = {str(o.source) + ":" + o.name: o for o in other.catalog_descriptor.items or []}

            for s in self.catalog_descriptor.items:
                o = other_items.get(str(s.source) + ":" + s.name)
                if o and not s.version.is_dirty and o.version.identifier == s.version.identifier:
                    # The prev item and self item have the same version IDs,
                    # so copy the prev item contents into the self item.
                    for k, v in o.model_dump().items():
                        setattr(s, k, v)
                else:
                    uninitialized_items.append(s)
        else:
            uninitialized_items += self.catalog_descriptor.items

        return uninitialized_items

    @staticmethod
    def load(catalog_path: pathlib.Path):
        """Load from a catalog_path JSON file."""
        with catalog_path.open("r") as fp:
            catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())
        return CatalogMem(catalog_descriptor=catalog_descriptor)

    def dump(self, catalog_path: pathlib.Path):
        """Save to a catalog_path JSON file."""
        self.catalog_descriptor.items.sort(key=lambda x: x.identifier)
        with catalog_path.open("w") as fp:
            fp.write(str(self.catalog_descriptor))
            fp.write("\n")

    def find(
        self,
        query: str,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
        item_name: str = "",
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # Return the exact tool instead of doing vector search in case item_name is provided
        if item_name != "":
            catalog = [x for x in self.catalog_descriptor.items if x.name == item_name]
            if len(catalog) != 0:
                return [SearchResult(entry=catalog[0], delta=1)]
            else:
                click.secho("No catalog items found with given conditions...", fg="yellow")
                return []

        import sentence_transformers
        import sklearn

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
        embedding_model = self.catalog_descriptor.embedding_model
        embedding_model_obj = sentence_transformers.SentenceTransformer(
            embedding_model, tokenizer_kwargs={"clean_up_tokenization_spaces": True}
        )
        query_embedding = embedding_model_obj.encode(query)
        deltas = sklearn.metrics.pairwise.cosine_similarity(
            X=[t.embedding for t in candidate_tools], Y=[query_embedding]
        )

        # Order results by their distance to the query (larger is "closer").
        results = [SearchResult(entry=candidate_tools[i], delta=deltas[i]) for i in range(len(deltas))]
        results = sorted(results, key=lambda t: t.delta, reverse=True)

        # Apply our limit clause.
        if limit > 0:
            results = results[:limit]
        return results
