import click
import logging
import typing

from ...record.descriptor import RecordDescriptor
from ...tool.descriptor import HTTPRequestToolDescriptor
from ...tool.descriptor import PythonToolDescriptor
from ...tool.descriptor import SemanticSearchToolDescriptor
from ...tool.descriptor import SQLPPQueryToolDescriptor
from .base import CatalogBase
from .base import SearchResult
from rosetta_core.annotation import AnnotationPredicate
from rosetta_core.defaults import DEFAULT_SCOPE_PREFIX
from rosetta_util.query import execute_query

logger = logging.getLogger(__name__)


class CatalogDB(CatalogBase):
    """Represents a catalog stored in a database."""

    def find(
        self,
        query: str,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
        bucket: str = "",
        kind: str = "tool",
        snapshot_id: typing.Union[str | None] = "all",
        cluster: any = "",
        meta: any = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # Generate embeddings for user query
        import sentence_transformers

        scope_name = DEFAULT_SCOPE_PREFIX + meta["embedding_model"].replace("/", "_")
        embedding_model_obj = sentence_transformers.SentenceTransformer(
            meta["embedding_model"], tokenizer_kwargs={"clean_up_tokenization_spaces": True}
        )
        query_embeddings = embedding_model_obj.encode(query).tolist()

        # --------Get all relevant items from catalog--------

        # Get annotations condition
        annotation_condition = annotations.__catalog_query_str__()

        # User has specified a snapshot id
        if snapshot_id != "all":
            filter_records_query = (
                f"SELECT a.* FROM ( SELECT t.*, SEARCH_META() as metadata FROM `{bucket}`.`{scope_name}`.`{kind}_catalog` as t "
                + "WHERE SEARCH(t, "
                + "{'query': {'match_none': {}},"
                + "'knn': [{'field': 'embedding',"
                + f"'vector': {query_embeddings},"
                + "'k': 10"
                + "}], 'size': 10, 'ctl': { 'timeout': 10 } }) ) AS a "
                + f"WHERE {annotation_condition} AND catalog_identifier='{snapshot_id}'"
                + f"LIMIT {limit};"
            )
        # No snapshot id has been mentioned
        else:
            filter_records_query = (
                f"SELECT a.* FROM ( SELECT t.*, SEARCH_META() as metadata FROM `{bucket}`.`{scope_name}`.`{kind}_catalog` as t "
                + "WHERE SEARCH(t, "
                + "{'query': {'match_none': {}},"
                + "'knn': [{'field': 'embedding',"
                + f"'vector': {query_embeddings},"
                + "'k': 10"
                + "}], 'size': 10, 'ctl': { 'timeout': 10 } }) ) AS a "
                + f"WHERE {annotation_condition} "
                + f"LIMIT {limit};"
            )

        # Execute query after filtering by catalog_identifier if provided
        res, err = execute_query(cluster, filter_records_query)
        if err is not None:
            click.secho(f"ERROR: {err}", fg="red")
            return []

        # List of catalog items from query
        catalog = []
        deltas = []
        for row in res.rows():
            kind = row["record_kind"]
            descriptor = ""
            deltas.append(row["metadata"]["score"])
            match kind:
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
        results = [SearchResult(entry=catalog[i], delta=deltas[i]) for i in range(len(deltas))]

        return results
