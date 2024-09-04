import click
import couchbase.cluster
import logging
import pydantic
import typing

from rosetta_core.annotation import AnnotationPredicate
from rosetta_core.catalog.catalog.base import CatalogBase
from rosetta_core.catalog.catalog.base import SearchResult
from rosetta_core.defaults import DEFAULT_SCOPE_PREFIX
from rosetta_core.record.descriptor import RecordDescriptor
from rosetta_core.tool.descriptor import HTTPRequestToolDescriptor
from rosetta_core.tool.descriptor import PythonToolDescriptor
from rosetta_core.tool.descriptor import SemanticSearchToolDescriptor
from rosetta_core.tool.descriptor import SQLPPQueryToolDescriptor
from rosetta_util.query import execute_query

logger = logging.getLogger(__name__)


class CatalogDB(pydantic.BaseModel, CatalogBase):
    """Represents a catalog stored in a database."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    cluster: couchbase.cluster.Cluster
    bucket: str
    kind: typing.Literal["tool", "prompt"]
    meta: dict

    # TODO (GLENN): Might need to add this to mem as well.
    snapshot_id: typing.Union[str | None] = "all"

    def find(
        self,
        query: str = None,
        name: str = "",
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        scope_name = DEFAULT_SCOPE_PREFIX + self.meta["embedding_model"].replace("/", "_")

        # Catalog item has to be queried directly
        if name != "":
            item_query = (
                f"SELECT a.* from `{self.bucket}`.`{scope_name}`.`{self.kind}_catalog` as a WHERE a.name = '{name}';"
            )

            res, err = execute_query(self.cluster, item_query)
            if err is not None:
                click.secho(f"ERROR: {err}", fg="red")
                return []
        else:
            # Generate embeddings for user query
            import sentence_transformers

            embedding_model_obj = sentence_transformers.SentenceTransformer(
                self.meta["embedding_model"], tokenizer_kwargs={"clean_up_tokenization_spaces": True}
            )
            query_embeddings = embedding_model_obj.encode(query).tolist()

            # ---------------------------------------------------------------------------------------- #
            #                         Get all relevant items from catalog                              #
            # ---------------------------------------------------------------------------------------- #

            # Get annotations condition
            annotation_condition = annotations.__catalog_query_str__() if annotations is not None else "1==1"

            # User has specified a snapshot id
            if self.snapshot_id != "all":
                filter_records_query = (  # TODO (GLENN): Use a """ """ string instead?
                    f"SELECT a.* FROM ( SELECT t.*, SEARCH_META() as metadata FROM `{self.bucket}`.`{scope_name}`.`{self.kind}_catalog` as t "
                    + "WHERE SEARCH(t, "
                    + "{'query': {'match_none': {}},"
                    + "'knn': [{'field': 'embedding',"
                    + f"'vector': {query_embeddings},"
                    + "'k': 10"
                    + "}], 'size': 10, 'ctl': { 'timeout': 10 } }) ORDER BY metadata.score DESC ) AS a "
                    + f"WHERE {annotation_condition} AND catalog_identifier='{self.snapshot_id}'"
                    + f"LIMIT {limit};"
                )
            # No snapshot id has been mentioned
            else:
                filter_records_query = (
                    f"SELECT a.* FROM ( SELECT t.*, SEARCH_META() as metadata FROM `{self.bucket}`.`{scope_name}`.`{self.kind}_catalog` as t "
                    + "WHERE SEARCH(t, "
                    + "{'query': {'match_none': {}},"
                    + "'knn': [{'field': 'embedding',"
                    + f"'vector': {query_embeddings},"
                    + "'k': 10"
                    + "}], 'size': 10, 'ctl': { 'timeout': 10 } }) ORDER BY metadata.score DESC ) AS a "
                    + f"WHERE {annotation_condition} "
                    + f"LIMIT {limit};"
                )

            # Execute query after filtering by catalog_identifier if provided
            res, err = execute_query(self.cluster, filter_records_query)
            if err is not None:
                click.secho(f"ERROR: {err}", fg="red")
                return []

        resp = list(res)

        # If result set is empty
        if len(resp) == 0:
            click.secho("No catalog items found with given conditions...", fg="yellow")
            return []

        # ---------------------------------------------------------------------------------------- #
        #                Format catalog items into SearchResults and child types                   #
        # ---------------------------------------------------------------------------------------- #

        # List of catalog items from query
        catalog = []
        deltas = []

        for row in resp:
            kind = row["record_kind"]
            descriptor = ""
            if name == "":
                deltas.append(row["metadata"]["score"])
            match kind:  # TODO (GLENN): Use RecordKind.SemanticSearch.value() instead (and same for the rest)
                case "semantic_search":
                    descriptor = SemanticSearchToolDescriptor.model_validate(row)
                case "python_function":
                    descriptor = PythonToolDescriptor.model_validate(row)
                case "sqlpp_query":
                    descriptor = SQLPPQueryToolDescriptor.model_validate(row)
                case "http_request":
                    descriptor = HTTPRequestToolDescriptor.model_validate(row)
                case _:
                    print("not a valid descriptor of ToolDescriptorUnion type")
            catalog.append(RecordDescriptor.model_validate(descriptor))

        # Final set of results
        if name != "":
            return [SearchResult(entry=catalog[0], delta=1)]

        return [SearchResult(entry=catalog[i], delta=deltas[i]) for i in range(len(deltas))]
