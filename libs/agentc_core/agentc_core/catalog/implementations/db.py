import couchbase.cluster
import json
import logging
import math
import pydantic
import re
import typing

from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog.descriptor import CatalogKind
from agentc_core.catalog.implementations.base import CatalogBase
from agentc_core.catalog.implementations.base import SearchResult
from agentc_core.config import LATEST_SNAPSHOT_VERSION
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.prompt.models import PromptDescriptor
from agentc_core.record.descriptor import RecordDescriptor
from agentc_core.record.descriptor import RecordKind
from agentc_core.remote.util.query import execute_query
from agentc_core.remote.util.query import execute_query_with_parameters
from agentc_core.remote.util.query import quote_sql_keyspace
from agentc_core.tool.descriptor import HTTPRequestToolDescriptor
from agentc_core.tool.descriptor import PythonToolDescriptor
from agentc_core.tool.descriptor import SemanticSearchToolDescriptor
from agentc_core.tool.descriptor import SQLPPQueryToolDescriptor
from agentc_core.version import VersionDescriptor
from couchbase.exceptions import KeyspaceNotFoundException
from couchbase.exceptions import ScopeNotFoundException

logger = logging.getLogger(__name__)


def _descriptor_from_row(row: dict[str, typing.Any]) -> RecordDescriptor:
    match row["record_kind"]:
        case RecordKind.SemanticSearch.value:
            return SemanticSearchToolDescriptor.model_validate(row)
        case RecordKind.PythonFunction.value:
            return PythonToolDescriptor.model_validate(row)
        case RecordKind.SQLPPQuery.value:
            return SQLPPQueryToolDescriptor.model_validate(row)
        case RecordKind.HTTPRequest.value:
            return HTTPRequestToolDescriptor.model_validate(row)
        case RecordKind.Prompt.value:
            return PromptDescriptor.model_validate(row)
        case _:
            kind = row["record_kind"]
            raise LookupError(f"Unknown record encountered of kind = '{kind}'!")


_VALID_INDEX_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")


def _sanitize_search_index_name(index_name: str) -> str:
    if not isinstance(index_name, str):
        raise TypeError("index_name must be a string")
    if not _VALID_INDEX_NAME_RE.fullmatch(index_name):
        raise ValueError("Invalid index_name format")
    return index_name


def _serialize_query_embeddings(query_embeddings: list[typing.Any]) -> str:
    if not isinstance(query_embeddings, list) or len(query_embeddings) == 0:
        raise ValueError("query_embeddings must be a non-empty list")

    cleaned_embeddings: list[float] = []
    for embedding in query_embeddings:
        if not isinstance(embedding, (int, float)):
            raise TypeError("query_embeddings must contain only numeric values")
        embedding_value = float(embedding)
        if not math.isfinite(embedding_value):
            raise ValueError("query_embeddings cannot contain NaN or Infinity")
        cleaned_embeddings.append(embedding_value)
    # JSON serialization produces a safe SQL++ array literal.
    return json.dumps(cleaned_embeddings, separators=(",", ":"))


class CatalogDB(pydantic.BaseModel, CatalogBase):
    """Represents a catalog stored in a database."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: EmbeddingModel
    cluster: couchbase.cluster.Cluster
    bucket: str
    kind: typing.Literal["tool", "prompt"]

    @pydantic.model_validator(mode="after")
    def _cluster_should_be_reachable(self) -> "CatalogDB":
        collection = DEFAULT_CATALOG_TOOL_COLLECTION if self.kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
        keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, collection)
        try:
            self.cluster.query(f"FROM {keyspace} SELECT 1 LIMIT 1;").execute()
            return self
        except (ScopeNotFoundException, KeyspaceNotFoundException) as e:
            raise ValueError("Catalog does not exist! Please run 'agentc publish' first.") from e

    def find(
        self,
        query: str = None,
        name: str = None,
        snapshot: str = None,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""
        collection = DEFAULT_CATALOG_TOOL_COLLECTION if self.kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
        sqlpp_query = None

        # Catalog item has to be queried directly
        if name is not None:
            if snapshot == LATEST_SNAPSHOT_VERSION:
                snapshot = self.version.identifier
            keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, collection)
            sqlpp_query = f"""
                FROM {keyspace} AS a
                WHERE a.name = $name AND a.catalog_identifier = $snapshot
                SELECT a.*;
            """
            res, err = execute_query_with_parameters(self.cluster, sqlpp_query, {"name": name, "snapshot": snapshot})
            if err is not None:
                logger.debug(err)
                return []
            query_embeddings = None

        else:
            # Generate embeddings for user query
            query_embeddings = self.embedding_model.encode(query)
            dim = len(query_embeddings)

            # ---------------------------------------------------------------------------------------- #
            #                         Get all relevant items from catalog                              #
            # ---------------------------------------------------------------------------------------- #

            # Get annotations condition
            annotation_condition = annotations.__catalog_query_str__() if annotations is not None else "1==1"

            # Index used (in the future, we may need to condition on the catalog schema version).
            idx = f"v2_AgentCatalog{self.kind.capitalize()}sEmbeddingIndex"
            keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, collection)
            index_name = f"{self.bucket}.{DEFAULT_CATALOG_SCOPE}.{idx}"
            safe_index_name = _sanitize_search_index_name(index_name)
            safe_query_embeddings = _serialize_query_embeddings(query_embeddings)

            # User has specified a snapshot id
            if snapshot is not None:
                if snapshot == LATEST_SNAPSHOT_VERSION:
                    snapshot = self.version.identifier

                sqlpp_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_SCORE() AS score
                        FROM {keyspace} AS t
                        WHERE SEARCH(
                            t,
                            {{
                                'query': {{ 'match_none': {{}} }},
                                'knn': [
                                    {{
                                        'field': 'embedding_{dim}',
                                        'vector': {safe_query_embeddings},
                                        'k': 10
                                    }}
                                ]
                            }},
                            {{
                                'index': '{safe_index_name}'
                            }}
                        )
                    ) AS a
                    WHERE {annotation_condition} AND a.catalog_identifier = $snapshot
                    ORDER BY a.score DESC
                    LIMIT $limit;
                """
                params = {
                    "snapshot": snapshot,
                    "limit": limit,
                }

            # No snapshot id has been mentioned
            else:
                sqlpp_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_SCORE() AS score
                        FROM {keyspace} as t
                        WHERE SEARCH(
                            t,
                            {{
                                'query': {{ 'match_none': {{}} }},
                                'knn': [
                                    {{
                                        'field': 'embedding_{dim}',
                                        'vector': {safe_query_embeddings},
                                        'k': 10
                                    }}
                                ]
                            }},
                            {{
                                'index': '{safe_index_name}'
                            }}
                        )
                    ) AS a
                    WHERE {annotation_condition}
                    ORDER BY a.score DESC
                    LIMIT $limit;
                """
                params = {"limit": limit}

            # Execute query after filtering by catalog_identifier if provided
            res, err = execute_query_with_parameters(self.cluster, sqlpp_query, params)
            if err is not None:
                logger.error(err)
                return []

        resp = list(res)

        # If result set is empty
        if len(resp) == 0:
            logger.debug(f"No catalog items found using the SQL++ query: {sqlpp_query}")
            return []

        # ---------------------------------------------------------------------------------------- #
        #                Format catalog items into SearchResults and child types                   #
        # ---------------------------------------------------------------------------------------- #

        # List of catalog items from query
        descriptors: list[RecordDescriptor] = []
        for row in resp:
            descriptors.append(_descriptor_from_row(row))

        # We compute the true cosine distance here (Couchbase uses a different score :-)).
        if name is not None:
            return [SearchResult(entry=descriptors[0], delta=1)]

        deltas = self.get_deltas(query_embeddings, [t.embedding for t in descriptors])
        results = [SearchResult(entry=descriptors[i], delta=deltas[i]) for i in range(len(deltas))]
        return sorted(results, key=lambda t: t.delta, reverse=True)

    def __iter__(self) -> typing.Iterator[RecordDescriptor]:
        """Return all items in a DB catalog."""
        collection = DEFAULT_CATALOG_TOOL_COLLECTION if self.kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
        keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, collection)
        query = f"FROM {keyspace} AS t SELECT t.*;"
        res, err = execute_query(self.cluster, query)
        if err is not None:
            logger.error(err)
            return
        for row in res:
            yield _descriptor_from_row(row)

    def __len__(self):
        collection = DEFAULT_CATALOG_TOOL_COLLECTION if self.kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
        keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, collection)
        query = f"FROM {keyspace} SELECT VALUE COUNT(*);"
        res, err = execute_query(self.cluster, query)
        if err is not None:
            logger.error(err)
            raise err
        for row in res:
            return row
        return None

    @property
    def version(self) -> VersionDescriptor:
        """Returns the latest version of the catalog."""
        kind = CatalogKind.Tool if self.kind == "tool" else CatalogKind.Prompt
        keyspace = quote_sql_keyspace(self.bucket, DEFAULT_CATALOG_SCOPE, DEFAULT_CATALOG_METADATA_COLLECTION)
        ts_query = f"""
            FROM {keyspace} AS t
            WHERE t.kind = $kind
            SELECT VALUE t.version
            ORDER BY STR_TO_MILLIS(t.version.timestamp) DESC
            LIMIT 1
        """
        res, err = execute_query_with_parameters(self.cluster, ts_query, {"kind": kind.value})
        if err is not None:
            logger.error(err)
            raise LookupError(f"No results found? -- Error: {err}")
        for row in res:
            return VersionDescriptor.model_validate(row)
        raise LookupError(
            f"Catalog version not found for kind = '{kind}'! Please run 'agentc publish' to create the catalog."
        )
