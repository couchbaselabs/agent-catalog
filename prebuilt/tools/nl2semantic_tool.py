import agentc
import couchbase.search as search

from agentc_core.secrets import get_secret
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.logic.vector_search import VectorQuery
from couchbase.logic.vector_search import VectorSearch
from couchbase.options import ClusterOptions
from couchbase.search import SearchOptions
from datetime import timedelta
from sentence_transformers import SentenceTransformer


def _get_couchbase_cluster() -> Cluster:
    authenticator = PasswordAuthenticator(
        username=get_secret("CB_USERNAME").get_secret_value(), password=get_secret("CB_PASSWORD").get_secret_value()
    )
    conn_string = get_secret("CB_CONN_STRING").get_secret_value()
    options = ClusterOptions(authenticator)
    options.apply_profile("wan_development")
    cluster = Cluster(conn_string, options)
    cluster.wait_until_ready(timedelta(seconds=15))
    return cluster


def _perform_vector_search(
    bucket: str, scope: str, collection: str, vector_field: str, query_vector: list[float], cluster: Cluster, limit: int
):
    bucket_obj = cluster.bucket(bucket)
    scope_obj = bucket_obj.scope(scope)

    vector_search = VectorSearch.from_vector_query(VectorQuery(vector_field, query_vector, num_candidates=limit))
    request = search.SearchRequest.create(vector_search)
    result = scope_obj.search(collection, request, SearchOptions())
    return result


def _get_documents_by_keys(
    bucket: str, scope: str, collection: str, keys: list[str], cluster: Cluster, answer_field: str
):
    bucket_obj = cluster.bucket(bucket)
    cb_coll = bucket_obj.scope(scope).collection(collection)

    docs = []
    for key in keys:
        result = cb_coll.get(key)
        result_dict = result.content_as[dict]
        if answer_field:
            docs.append(result_dict[answer_field])
        else:
            docs.append(result_dict)

    return docs


@agentc.tool
def vector_search_tool(
    bucket: str,
    scope: str,
    collection: str,
    natural_language_query: str,
    num_docs: int = 2,
    model_name: str = "flax-sentence-embeddings/st-codesearch-distilroberta-base",
    vector_field: str = "",
    answer_field: str = None,
) -> list[dict]:
    """Takes in natural language query and does vector search on using it on the documents present in Couchbase cluster based on num_docs parameter value."""

    # Extract schema
    cluster = _get_couchbase_cluster()
    if cluster is None:
        return []

    # Perform vector search
    model = SentenceTransformer(model_name)
    query_vector = model.encode(natural_language_query).tolist()
    results = _perform_vector_search(bucket, scope, collection, vector_field, query_vector, cluster, limit=num_docs)

    row_ids = []
    for row in results.rows():
        row_ids.append(row.id)

    data = _get_documents_by_keys(bucket, scope, collection, keys=row_ids, cluster=cluster, answer_field=answer_field)
    return data
