from couchbase.exceptions import CouchbaseException
from couchbase.options import QueryOptions


def execute_query(cluster, exec_query) -> tuple[any, Exception | None]:
    try:
        print("Executing query...")
        result = cluster.query(exec_query, QueryOptions(metrics=True))
        return result, None
    except CouchbaseException as e:
        return None, e
