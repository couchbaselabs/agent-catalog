from collections import defaultdict

import abc
import json
import pathlib
import typing
import pydantic
import sklearn

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
    def diff(self, source: 'MemCatalogRef', repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        """ Returns the (newer, deleted) items in the source MemCatalogRef
            compared to the items in self.

            From the results of diff(), later steps can UPSERT the newer
            items into self and DELETE the deleted items from self.

            The items in the source MemCatalogRef can be 'bare', in that
            they might not yet have augmentations and/or vector embeddings.

            The repo_commit_id of source items vs self items are compared, and
            the repo object (e.g., a git repo) is consulted for deeper comparisons.
        """

        raise NotImplementedError("CatalogRef.diff()")

    @abc.abstractmethod
    def update(self, meta, repo_commit_id: str,
               newer: list[ToolDescriptor], deleted: list[ToolDescriptor], repo):
        """ Updates self from newer items (will be UPSERT'ed) and deleted items.
        """

        raise NotImplementedError("CatalogRef.update()")


class MemCatalogRef(CatalogRef):
    """ Represents an in-memory catalog ref. """

    catalog_path: pathlib.Path

    catalog_descriptor: CatalogDescriptor

    def load(self, catalog_path: pathlib.Path) -> typing.Self:
        self.catalog_path = catalog_path

        with self.catalog_path.open('r') as fp:
            self.catalog_descriptor = CatalogDescriptor.model_validate_json(fp.read())

        return self

    def save(self, catalog_path: pathlib.Path):
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

        # TODO: Expose max param out to command-line rosetta find --max N QUERY.

        available_tools = self.catalog_descriptor.items

        embedding_model = self.catalog_descriptor.embedding_model

        import sentence_transformers

        embedding_model_obj = sentence_transformers.SentenceTransformer(embedding_model)

        query_embedding = embedding_model_obj.encode(query)

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

    def diff(self, source: typing.Self, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        newer, deleted = [], [] # TODO.

        return (newer, deleted)

    def update(self, meta, repo_commit_id: str,
               newer: list[ToolDescriptor], deleted: list[ToolDescriptor], repo):
        if self.catalog_descriptor is None:
            self.catalog_descriptor = CatalogDescriptor(
                catalog_schema_version=meta["catalog_schema_version"],
                embedding_model=meta["embedding_model"],
                repo_commit_id=repo_commit_id,
                items=[]
            )

        # A lookup dict m of our existing items keyed by "source:name".
        m = defaultdict(list)
        for x in self.catalog_descriptor.items:
            m[x.source + ':' + x.name].append(x)

        # Update m based on newer.
        for x in newer or []:
            latest = x.model_copy()
            latest.deleted = False

            m[x.source + ':' + x.name].append(latest)

        # Update m based on deleted.
        for x in deleted or []:
            tombstone = x.model_copy()
            tombstone.deleted = True

            m[x.source + ':' + x.name].append(tombstone)

        # TODO: Some callers may want append-only behavior, where we
        # keep all our existing items unchanged and only append new
        # items (updates are new items) -- turn this into a parameter?
        append_only = False

        items = []
        for a in m.values():
            if append_only:
                items += a
            else:
                items.append(a[-1])

        items.sort(key=lambda x: x.identifier)

        self.catalog_descriptor.items = items

        self.cache_clear()


class DBCatalogRef(CatalogRef):
    """ Represents a catalog stored in a database. """

    # TODO: This probably has fields of conn info, etc.

    def find(self, query: str,
             max: typing.Union[int | None] = 1) -> list[FoundItem]:
        """ Returns the catalog items that best match a query. """

        return [] # TODO: SQL++ and vector index searches likely are involved here.

    def diff(self, source: MemCatalogRef, repo) -> typing.Tuple[list[ToolDescriptor], list[ToolDescriptor]]:
        newer, deleted = [], [] # TODO.

        return (newer, deleted)

    def update(self, meta, repo_commit_id: str,
               newer: list[ToolDescriptor], deleted: list[ToolDescriptor], repo):
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
