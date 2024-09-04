import click
import logging
import pathlib
import pydantic
import typing

from ...annotation import AnnotationPredicate
from ...catalog.descriptor import CatalogDescriptor
from ...version import VersionDescriptor
from .base import CatalogBase
from .base import SearchResult

logger = logging.getLogger(__name__)


class CatalogMem(pydantic.BaseModel, CatalogBase):
    """Represents an in-memory catalog."""

    catalog_descriptor: CatalogDescriptor
    embedding_model: typing.Optional[str] = None

    # TODO (GLENN): it might be better to refactor this into the constructor.
    @staticmethod
    def load(catalog_path: pathlib.Path, embedding_model: str = None):
        """Load from a catalog_path JSON file."""
        with catalog_path.open("r") as fp:
            catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())
        return CatalogMem(catalog_descriptor=catalog_descriptor, embedding_model=embedding_model)

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
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # Return the exact tool instead of doing vector search in case name is provided
        if name is not None:
            catalog = [x for x in self.catalog_descriptor.items if x.name == name]
            if len(catalog) != 0:
                return [SearchResult(entry=catalog[0], delta=1)]
            else:
                click.secho(f"No catalog items found with name '{name}'", fg="yellow")
                return []

        if self.embedding_model is None:
            raise RuntimeError("Embedding model not set!")

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
        embedding_model_obj = sentence_transformers.SentenceTransformer(
            self.embedding_model, tokenizer_kwargs={"clean_up_tokenization_spaces": True}
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

    @property
    def version(self) -> VersionDescriptor:
        return self.catalog_descriptor.version
