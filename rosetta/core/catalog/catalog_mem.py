import pathlib
import pydantic

from .catalog_base import CatalogBase, SearchResult
from ..catalog.descriptor import CatalogDescriptor, REPO_DIRTY
from ..record.descriptor import RecordDescriptor


class CatalogMem(pydantic.BaseModel, CatalogBase):
    """ Represents an in-memory catalog. """
    catalog_descriptor: CatalogDescriptor = None

    def init_from(self, other: 'CatalogMem') -> list[RecordDescriptor]:
        """ Initialize the items in self by copying over attributes from
            items found in other that have the exact same repo_commit_id's.

            Returns a list of uninitialized items. """

        uninitialized_items = []
        if other and other.catalog_descriptor:
            # A lookup dict of items keyed by "source:name".
            other_items = {str(o.source) + ':' + o.name: o
                           for o in other.catalog_descriptor.items or []}

            for s in self.catalog_descriptor.items:
                o = other_items.get(str(s.source) + ':' + s.name)
                if o and s.repo_commit_id != REPO_DIRTY and \
                        o.repo_commit_id == s.repo_commit_id:
                    # The prev item and self item have the same repo_commit_id's,
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
        """ Load from a catalog_path JSON file. """
        with catalog_path.open('r') as fp:
            catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())
        return CatalogMem(catalog_descriptor=catalog_descriptor)

    def dump(self, catalog_path: pathlib.Path):
        """ Save to a catalog_path JSON file. """
        self.catalog_descriptor.items.sort(key=lambda x: x.identifier)

        # TODO: We should have a specialized json format here, where currently
        # the vector numbers each take up their own line -- and, instead, we want
        # the array of vector numbers to be all on one line, so that it's more
        # usable for humans and so that 'git diff' outputs are more useful.
        j = self.catalog_descriptor.model_dump_json(round_trip=True, indent=2)
        with catalog_path.open('w') as fp:
            fp.write(j)
            fp.write('\n')

    def find(self, query: str, limit: int = 1) -> list[SearchResult]:
        """ Returns the catalog items that best match a query. """
        import sentence_transformers
        import sklearn

        # Compute the distance of each tool in the catalog to the query.
        available_tools = [x for x in self.catalog_descriptor.items]
        embedding_model = self.catalog_descriptor.embedding_model
        embedding_model_obj = sentence_transformers.SentenceTransformer(
            embedding_model,
            tokenizer_kwargs={'clean_up_tokenization_spaces': True}
        )
        query_embedding = embedding_model_obj.encode(query)
        deltas = sklearn.metrics.pairwise.cosine_similarity(
            X=[t.embedding for t in available_tools],
            Y=[query_embedding]
        )

        # Order results by their distance to the query (larger is "closer").
        results = [
            SearchResult(
                record_descriptor=available_tools[i],
                delta=deltas[i]
            ) for i in range(len(deltas))
        ]
        results = sorted(results, key=lambda t: t.delta, reverse=True)

        # Apply our limit clause.
        if limit > 0:
            results = results[:limit]
        return results
