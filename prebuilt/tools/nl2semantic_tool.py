import agentc

from sentence_transformers import SentenceTransformer


@agentc.tool
def vector_search_tool(
    bucket,
    collection,
    scope,
    username,
    password,
    cluster_url,
    natural_language_query,
    model,
    vector_field,
    answer_field=None,
):
    """run vector search given a natural language query"""
    import couchbase.search as search

    from couchbase.auth import PasswordAuthenticator
    from couchbase.cluster import Cluster
    from couchbase.exceptions import CouchbaseException
    from couchbase.options import ClusterOptions
    from couchbase.options import SearchOptions
    from couchbase.vector_search import VectorQuery
    from couchbase.vector_search import VectorSearch
    from datetime import timedelta

    # logger = logging.getLogger()

    cluster = None
    if cluster_url == "couchbase://127.0.0.1" or cluster_url == "couchbase://localhost":
        auth = PasswordAuthenticator(username, password)
        options = ClusterOptions(auth)
        options.apply_profile("wan_development")
    else:
        auth = PasswordAuthenticator(username, password, cert_path="certificates/cert.pem")
        options = ClusterOptions(auth)
        options.apply_profile("wan_development")

    try:
        cluster = Cluster(cluster_url, options)
        cluster.wait_until_ready(timedelta(seconds=15))
    except CouchbaseException as e:
        return {"status": False, "message": f"Error connecting to couchbase : {e}"}

    def perform_vector_search(scope, collection, vector_field, query_vector, limit=2):
        cluster.wait_until_ready(timedelta(seconds=5))

        bucket = cluster.bucket(bucket_name)
        scope = bucket.scope(scope)

        vector_search = VectorSearch.from_vector_query(VectorQuery(vector_field, query_vector, num_candidates=limit))
        request = search.SearchRequest.create(vector_search)
        result = scope.search(collection, request, SearchOptions())
        return result

    def get_document_by_keys(scope, collection, keys):
        cluster.wait_until_ready(timedelta(seconds=5))

        bucket = cluster.bucket(bucket_name)
        cb_coll = bucket.scope(scope).collection(collection)

        dict_results = []
        for key in keys:
            try:
                result = cb_coll.get(key)
                result_dict = result.content_as[dict]
                if answer_field:
                    dict_results.append(result_dict[answer_field])
                else:
                    dict_results.append(result_dict)
            except Exception as e:
                return {"status": False, "message": f"Error in document query : {e}"}
        return dict_results

    query_vector = model.encode(natural_language_query).tolist()
    results = perform_vector_search(scope, collection, vector_field, query_vector, limit=1)
    row_ids = []
    for row in results.rows():
        print(f"Score: {row.score}")
        print(f"Document Id: {row.id}")

        row_ids.append(row.id)

    data = get_document_by_keys(scope, collection, row_ids)
    return data


if __name__ == "__main__":
    bucket_name = "agentc-search-test"
    scope = "tools-catalog"
    model = SentenceTransformer("flax-sentence-embeddings/st-codesearch-distilroberta-base")
    natural_language_query = "train a model"
    vector_field = "embedding"

    data = vector_search_tool(
        "agentc-search-test",
        "glaive_v2_dataset_df_v1_small_train-langchaindescription-M1",
        "tools-catalog",
        "Administrator",
        "password",
        "couchbase://127.0.0.1",
        natural_language_query,
        model,
        vector_field,
    )
    print(data)
