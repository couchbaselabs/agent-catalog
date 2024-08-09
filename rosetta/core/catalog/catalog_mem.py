import pathlib
import typing

from .catalog_base import CatalogBase, FoundItem
from ..catalog.descriptor import CatalogDescriptor, REPO_DIRTY
from ..record.descriptor import RecordDescriptor


class CatalogMem(CatalogBase):
    """ Represents an in-memory catalog. """

    catalog_path: pathlib.Path

    catalog_descriptor: CatalogDescriptor

    def __init__(self,
                 catalog_path: pathlib.Path = None,
                 catalog_descriptor: CatalogDescriptor = None):
        self.catalog_path = catalog_path
        self.catalog_descriptor = catalog_descriptor

    def init_from(self, other: typing.Self) -> list[RecordDescriptor]:
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

        return uninitialized_items

    def load(self, catalog_path: pathlib.Path) -> typing.Self:
        """ Load from a catalog_path JSON file. """

        self.catalog_path = catalog_path

        with self.catalog_path.open('r') as fp:
            self.catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())

        return self

    def save(self, catalog_path: pathlib.Path):
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

    def find(self, query: str, max: int = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        available_tools = [x for x in self.catalog_descriptor.items]

        embedding_model = self.catalog_descriptor.embedding_model

        import sentence_transformers

        embedding_model_obj = sentence_transformers.SentenceTransformer(embedding_model)

        query_embedding = embedding_model_obj.encode(query)

        import sklearn

        deltas = sklearn.metrics.pairwise.cosine_similarity(
            X=[t.embedding for t in available_tools],
            Y=[query_embedding]
        )

        # Order results by their distance to the query (larger is "closer").
        results = [FoundItem(record_descriptor=available_tools[i],
                             delta=deltas[i])
                   for i in range(len(deltas))]

        results = sorted(results, key=lambda t: t.delta, reverse=True)

        if max > 0:
            results = results[:max]

        return results
