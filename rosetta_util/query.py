from couchbase.exceptions import CouchbaseException
from couchbase.options import QueryOptions


def execute_query(cluster, keyspace, exec_query) -> tuple[any, Exception | None]:
    bucket = cluster.bucket(keyspace.bucket)
    collection = bucket.name(keyspace.collection)
    try:
        print("Executing query...")
        result = cluster.query(exec_query, QueryOptions(metrics=True))
        return result, None
    except CouchbaseException as e:
        return None, e
