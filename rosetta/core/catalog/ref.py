from collections import defaultdict

import abc
import pathlib
import typing
import pydantic

from ..tool.types.descriptor import ToolDescriptor

from .descriptor import CatalogDescriptor


class FoundItem(pydantic.BaseModel):
    """ A result item in the results from a CatalogRef.find(). """

    tool_descriptor: ToolDescriptor

    # TODO: A FoundItem might one day also contain a similarity score
    # or extra information -- such as to help with any further
    # processing of results (e.g., reranking)?

    delta: typing.Any


class CatalogRef(abc.ABC):
    """ An abstract interface for a catalog reference. """

    @abc.abstractmethod
    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        # TODO: The find() method might likely one day need additional,
        # optional params, perhaps to query on tags, labels, annotations,
        # user credentials (for ACL's), etc.?

        raise NotImplementedError("CatalogRef.find()")

    @abc.abstractmethod
    def diff(self, other: 'MemCatalogRef', repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        """ Compare items from self to items from other.

            Returns (items_to_upsert, items_to_delete) lists, where the
            items_to_upsert list holds items from the other MemCatalogRef,
            and the items_to_delete list holds items from the self MemCatalogRef.

            The items in the other MemCatalogRef can be 'bare', in that
            they might not yet have augmentations and/or vector embeddings.

            The repo_commit_id of other items vs self items are compared, and the
            repo object (e.g., a git repo) may be consulted for deeper comparisons.
        """

        raise NotImplementedError("CatalogRef.diff()")

    @abc.abstractmethod
    def update(self, meta, repo_commit_id: str,
               items_to_upsert: list[ToolDescriptor],
               items_to_delete: list[ToolDescriptor],
               repo):
        """ Updates self from the items to upsert and delete.
        """

        raise NotImplementedError("CatalogRef.update()")


class MemCatalogRef(CatalogRef):
    """ Represents an in-memory catalog ref. """

    catalog_path: pathlib.Path

    catalog_descriptor: CatalogDescriptor

    # A cached lookup dict of our catalog_descriptor's items keyed by "source:name".
    _cache_items: typing.Union[defaultdict | None]

    def __init__(self):
        self.catalog_path = None
        self.catalog_descriptor = None
        self._cache_items = None

    def _cache_items_release(self):
        self._cache_items = None

    def _cache_items_load(self, fresh=False):
        if self._cache_items is None or fresh:
            self._cache_items = defaultdict(list)
            for x in self.catalog_descriptor.items:
                self._cache_items[str(x.source) + ':' + x.name].append(x)

        return self._cache_items

    def load(self, catalog_path: pathlib.Path) -> typing.Self:
        """ Load from a catalog_path JSON file. """

        self.catalog_path = catalog_path

        with self.catalog_path.open('r') as fp:
            self.catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())

        self._cache_items_release()

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

    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        available_tools = [x for x in self.catalog_descriptor.items
                           if not bool(x.deleted)]

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
        results = [FoundItem(tool_descriptor=available_tools[i],
                             delta=deltas[i])
                   for i in range(len(deltas))]

        results = sorted(results, key=lambda t: t.delta, reverse=True)

        if max > 0:
            results = results[:max]

        return results

    def diff(self, other: typing.Self, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        if not other or not other.catalog_descriptor:
            return [], []

        items_to_upsert, items_to_delete = [], []

        # A lookup dict of items keyed by "source:name".
        m = self._cache_items_load(fresh=True)

        # TODO: The following assumes we're on the same branch
        # or sequential lineage of commits -- so branching
        # complexities need to be considered another day.

        other_source_names = set()

        for o in other.catalog_descriptor.items or []:
            source_name = str(o.source) + ':' + o.name

            other_source_names.add(source_name)

            xs: list[ToolDescriptor] = m.get(source_name, [])
            if len(xs) > 0:
                s = xs[-1]

                if bool(o.deleted):
                    if bool(s.deleted):
                        # It's deleted in self, and it's deleted in other, so NO-OP.
                        pass
                    else:
                        # It's active in self, and it's deleted in other, so DELETE.
                        items_to_delete.append(o)
                else:
                    if bool(s.deleted):
                        # It's deleted in self, and it's active in other, so UPSERT.
                        items_to_upsert.append(o)
                    else:
                        # It's active in self, and it's active in other, so compare them...
                        if s.repo_commit_id == o.repo_commit_id:
                            # They have the same repo_commit_id's, so NO-OP.
                            pass
                        else:
                            # The have different repo_commit_id's, so UPSERT.
                            items_to_upsert.append(o)
            else:
                if bool(o.deleted):
                    # It's not in self, and it's deleted in other, so NO-OP.
                    pass
                else:
                    # It's not in self, and it's active in other, so UPSERT.
                    items_to_upsert.append(o)

        # Any active items in self that are not in other should be DELETE'ed.
        for s in self.catalog_descriptor.items or []:
            if not bool(s.deleted):
                source_name = str(s.source) + ':' + s.name

                if source_name not in other_source_names:
                    # The self has an item that's not in other, so it's a DELETE.
                    d = s.model_copy()
                    d.deleted = True

                    # TODO: We should find the actual commit id
                    # of the deletion from the repo.
                    # d.repo_commit_id = ???

                    items_to_delete.append(d)

        return (items_to_upsert, items_to_delete)

    def update(self, meta, repo_commit_id: str,
               items_to_upsert: list[ToolDescriptor],
               items_to_delete: list[ToolDescriptor],
               repo):
        if self.catalog_descriptor is None:
            self.catalog_descriptor = CatalogDescriptor(
                catalog_schema_version=meta["catalog_schema_version"],
                embedding_model=meta["embedding_model"],
                repo_commit_id=repo_commit_id,
                items=[])

        # A lookup dict of items keyed by "source:name".
        m = self._cache_items_load()

        # Since we own the lookup dict now and will mutate it.
        self._cache_items_release()

        # Update m based on items_to_delete.
        for x in items_to_delete or []:
            x.deleted = True
            m[str(x.source) + ':' + x.name].append(x)

        # Update m based on items_to_upsert.
        for x in items_to_upsert or []:
            x.deleted = False
            m[str(x.source) + ':' + x.name].append(x)

        items = []
        for xs in m.values():
            items.append(xs[-1])

        items.sort(key=lambda x: x.identifier)

        self.catalog_descriptor.catalog_schema_version = meta["catalog_schema_version"]
        self.catalog_descriptor.embedding_model = meta["embedding_model"]
        self.catalog_descriptor.repo_commit_id = repo_commit_id
        self.catalog_descriptor.items = items


class DBCatalogRef(CatalogRef):
    """ Represents a catalog stored in a database. """

    # TODO: This probably has fields of conn info, etc.

    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.

    def diff(self, other: MemCatalogRef, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        items_to_upsert, items_to_delete = [], [] # TODO.

        return (items_to_upsert, items_to_delete)

    def update(self, meta, repo_commit_id: str,
               items_to_upsert: list[ToolDescriptor],
               items_to_delete: list[ToolDescriptor],
               repo):
        pass # TODO.


class ChainedCatalogRef(CatalogRef):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    chain: list[CatalogRef]

    def __init__(self, chain):
        self.chain = chain

    def find(self, query) -> list[ToolDescriptor]:
        # TODO: This might roughly look something like...

        results = []

        for c in self.chain:
            results_c = c.find(query)

            # TODO: Filter out entries from results_c which
            # are shadowed by the entries in the existing results.

            results += results_c

        return results
