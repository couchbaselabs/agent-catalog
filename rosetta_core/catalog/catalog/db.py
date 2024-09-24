import couchbase.cluster
import logging
import pydantic
import typing

from ..annotation import AnnotationPredicate
from ..catalog.descriptor import CatalogDescriptor
from .catalog_base import CatalogBase
from .catalog_base import SearchResult
from rosetta_cmd.models import CouchbaseConnect
from rosetta_core.annotation import AnnotationPredicate
from rosetta_core.catalog.catalog.base import CatalogBase
from rosetta_core.catalog.catalog.base import SearchResult
from rosetta_core.defaults import DEFAULT_SCOPE_PREFIX
from rosetta_core.prompt.models import JinjaPromptDescriptor
from rosetta_core.prompt.models import RawPromptDescriptor
from rosetta_core.record.descriptor import RecordKind
from rosetta_core.tool.descriptor import HTTPRequestToolDescriptor
from rosetta_core.tool.descriptor import PythonToolDescriptor
from rosetta_core.tool.descriptor import SemanticSearchToolDescriptor
from rosetta_core.tool.descriptor import SQLPPQueryToolDescriptor
from rosetta_core.version import VersionDescriptor
from rosetta_util.query import execute_query
from rosetta_util.query import execute_query_with_parameters

logger = logging.getLogger(__name__)


class CatalogDB(pydantic.BaseModel, CatalogBase):
    """Represents a catalog stored in a database."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    cluster: couchbase.cluster.Cluster
    bucket: str
    kind: typing.Literal["tool", "prompt"]
    embedding_model: str

    # TODO (GLENN): Might need to add this to mem as well.
    snapshot_id: typing.Union[str | None] = "all"

    @pydantic.model_validator(mode="after")
    def cluster_should_be_reachable(self) -> "CatalogDB":
        try:
            # TODO (GLENN): Factor our embedding model here
            collection_name = f"{self.kind}_catalog"
            self.cluster.query(
                f"""
                FROM   `{self.bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{collection_name}`
                SELECT 1
                LIMIT  1;
            """,
            ).execute()
            return self
        except ScopeNotFoundException as e:
            raise ValueError("Catalog does not exist! Please run 'rosetta publish' first.") from e

    def find(
        self,
        query: str = None,
        name: str = None,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
        catalog_schema_version: str = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # Catalog item has to be queried directly
        if name is not None:
            # TODO (GLENN): Need to add some validation around bucket (to prevent injection)
            # TODO (GLENN): Need to add some validation around name (to prevent injection)
            item_query = f"SELECT a.* from `{self.bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{self.kind}_catalog` as a WHERE a.name = $name;"

            res, err = execute_query_with_parameters(self.cluster, item_query, {"name": name})
            if err is not None:
                logger.error(err)
                return []
        else:
            # Generate embeddings for user query
            import sentence_transformers

            embedding_model_obj = sentence_transformers.SentenceTransformer(
                self.embedding_model, tokenizer_kwargs={"clean_up_tokenization_spaces": True}
            )
            query_embeddings = embedding_model_obj.encode(query).tolist()
            dim = len(query_embeddings)
            print(dim)

            # ---------------------------------------------------------------------------------------- #
            #                         Get all relevant items from catalog                              #
            # ---------------------------------------------------------------------------------------- #

            # Get annotations condition
            annotation_condition = annotations.__catalog_query_str__() if annotations is not None else "1==1"

            # Index used
            idx = f"rosetta_{self.kind}_index_{catalog_schema_version}"

            # User has specified a snapshot id
            if self.snapshot_id != "all":
                filter_records_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_META() as metadata
                        FROM `{self.bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{self.kind}_catalog` as t
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
                                'index': '{self.bucket}.{DEFAULT_SCOPE_PREFIX}.{idx}'
                            }}
                        )
                        ORDER BY metadata.score DESC
                    ) AS a
                    WHERE {annotation_condition} AND catalog_identifier='{self.snapshot_id}'
                    LIMIT {limit};
                """

            # No snapshot id has been mentioned
            else:
                filter_records_query = f"""
                    SELECT a.* FROM (
                        SELECT t.*, SEARCH_META() as metadata
                        FROM `{self.bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{self.kind}_catalog` as t
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
                                'index': '{self.bucket}.{DEFAULT_SCOPE_PREFIX}.{idx}'
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
            logger.warning("No catalog items found with given conditions...")
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
        """Returns the lates version of the kind catalog"""
        ts_query = f"""
            FROM     `{self.bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{self.kind}_catalog` AS t
            SELECT   VALUE  t.version
            ORDER BY META().cas DESC
            LIMIT    1
        """

        res, err = execute_query(self.cluster, ts_query)
        if err is not None:
            logger.error(err)
            raise LookupError(f"No results found? -- Error: {err}")
        return VersionDescriptor.model_validate(next(iter(res)))
