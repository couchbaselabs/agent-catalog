import couchbase.cluster
import logging
import pydantic
import typing

from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog.catalog.base import LATEST_SNAPSHOT_VERSION
from agentc_core.catalog.catalog.base import CatalogBase
from agentc_core.catalog.catalog.base import SearchResult
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.embedding.embedding import EmbeddingModel
from agentc_core.prompt.models import JinjaPromptDescriptor
from agentc_core.prompt.models import RawPromptDescriptor
from agentc_core.record.descriptor import RecordKind
from agentc_core.tool.descriptor import HTTPRequestToolDescriptor
from agentc_core.tool.descriptor import PythonToolDescriptor
from agentc_core.tool.descriptor import SemanticSearchToolDescriptor
from agentc_core.tool.descriptor import SQLPPQueryToolDescriptor
from agentc_core.util.query import execute_query
from agentc_core.util.query import execute_query_with_parameters
from agentc_core.version import VersionDescriptor
from couchbase.exceptions import ScopeNotFoundException

logger = logging.getLogger(__name__)


class CatalogDB(pydantic.BaseModel, CatalogBase):
    """Represents a catalog stored in a database."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: EmbeddingModel
    cluster: couchbase.cluster.Cluster
    bucket: str
    kind: typing.Literal["tool", "prompt"]

    # Note: If latest_version is None and a user does not specify a snapshot, we will raise an error.
    latest_version: typing.Optional[VersionDescriptor] = None

    @pydantic.model_validator(mode="after")
    def cluster_should_be_reachable(self) -> "CatalogDB":
        try:
            # TODO (GLENN): Factor our embedding model here
            collection_name = f"{self.kind}_catalog"
            self.cluster.query(
                f"""
                FROM   `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection_name}`
                SELECT 1
                LIMIT  1;
            """,
            ).execute()
            return self
        except ScopeNotFoundException as e:
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

        # Catalog item has to be queried directly
        if name is not None and snapshot is not None:
            # TODO (GLENN): Need to add some validation around bucket (to prevent injection)
            # TODO (GLENN): Need to add some validation around name (to prevent injection)
            item_query = f"""
                FROM `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{self.kind}_catalog` AS a
                WHERE a.name = $name AND a.catalog_identifier = $snapshot
                SELECT a.*;
            """
            res, err = execute_query_with_parameters(self.cluster, item_query, {"name": name, "snapshot": snapshot})
            if err is not None:
                logger.error(err)
                return []

        elif name is not None:
            item_query = f"""
                FROM `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{self.kind}_catalog` AS a
                WHERE a.name = $name
                SELECT a.*;
            """
            res, err = execute_query_with_parameters(self.cluster, item_query, {"name": name})
            if err is not None:
                logger.error(err)
                return []

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
            idx = f"v1_agent_catalog_{self.kind}_index"

            # User has specified a snapshot id
            if snapshot is not None:
                if snapshot == LATEST_SNAPSHOT_VERSION and (
                    self.latest_version is None or self.latest_version.identifier is None
                ):
                    raise ValueError("No latest version found for the catalog!")
                elif snapshot == LATEST_SNAPSHOT_VERSION:
                    snapshot = self.latest_version.identifier

                filter_records_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_META() as metadata
                        FROM `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{self.kind}_catalog` as t
                        WHERE SEARCH(
                            t,
                            {{
                                'query': {{ 'match_none': {{}} }},
                                'knn': [
                                    {{
                                        'field': 'embedding_{dim}',
                                        'vector': {query_embeddings},
                                        'k': 10
                                    }}
                                ],
                                'size': 10,
                                'ctl': {{ 'timeout': 10 }}
                            }},
                            {{
                                'index': '{self.bucket}.{DEFAULT_CATALOG_SCOPE}.{idx}'
                            }}
                        )
                        ORDER BY metadata.score DESC
                    ) AS a
                    WHERE {annotation_condition} AND a.catalog_identifier="{snapshot}"
                    LIMIT {limit};
                """

            # No snapshot id has been mentioned
            else:
                filter_records_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_META() as metadata
                        FROM `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{self.kind}_catalog` as t
                        WHERE SEARCH(
                            t,
                            {{
                                'query': {{ 'match_none': {{}} }},
                                'knn': [
                                    {{
                                        'field': 'embedding_{dim}',
                                        'vector': {query_embeddings},
                                        'k': 10
                                    }}
                                ],
                                'size': 10,
                                'ctl': {{ 'timeout': 10 }}
                            }},
                            {{
                                'index': '{self.bucket}.{DEFAULT_CATALOG_SCOPE}.{idx}'
                            }}
                        )
                        ORDER BY metadata.score DESC
                    ) AS a
                    WHERE {annotation_condition}
                    LIMIT {limit};
                """

            # Execute query after filtering by catalog_identifier if provided
            res, err = execute_query(self.cluster, filter_records_query)
            if err is not None:
                logger.error(err)
                return []

        resp = list(res)

        # If result set is empty
        if len(resp) == 0:
            logger.debug("No catalog items found with given conditions...")
            return []

        # ---------------------------------------------------------------------------------------- #
        #                Format catalog items into SearchResults and child types                   #
        # ---------------------------------------------------------------------------------------- #

        # List of catalog items from query
        results = []
        for row in resp:
            delta = row["metadata"]["score"] if name is None else 1
            match row["record_kind"]:
                case RecordKind.SemanticSearch.value:
                    descriptor = SemanticSearchToolDescriptor.model_validate(row)
                case RecordKind.PythonFunction.value:
                    descriptor = PythonToolDescriptor.model_validate(row)
                case RecordKind.SQLPPQuery.value:
                    descriptor = SQLPPQueryToolDescriptor.model_validate(row)
                case RecordKind.HTTPRequest.value:
                    descriptor = HTTPRequestToolDescriptor.model_validate(row)
                case RecordKind.RawPrompt.value:
                    descriptor = RawPromptDescriptor.model_validate(row)
                case RecordKind.JinjaPrompt.value:
                    descriptor = JinjaPromptDescriptor.model_validate(row)
                case _:
                    kind = row["record_kind"]
                    raise LookupError(f"Unknown record encountered of kind = '{kind}'!")
            results.append(SearchResult(entry=descriptor, delta=delta))
        return results

    @property
    def version(self) -> VersionDescriptor:
        """Returns the latest version of the kind catalog"""
        ts_query = f"""
            FROM     `{self.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{self.kind}_catalog` AS t
            SELECT   VALUE  t.version
            ORDER BY META().cas DESC
            LIMIT    1
        """

        res, err = execute_query(self.cluster, ts_query)
        if err is not None:
            logger.error(err)
            raise LookupError(f"No results found? -- Error: {err}")
        return VersionDescriptor.model_validate(next(iter(res)))
