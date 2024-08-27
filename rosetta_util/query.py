from couchbase.exceptions import CouchbaseException
from couchbase.options import QueryOptions


def execute_query(cluster, exec_query) -> tuple[any, Exception | None]:
    """Execute a given query"""

    try:
        result = cluster.query(exec_query, QueryOptions(metrics=True))
        return result, None
    except CouchbaseException as e:
        return None, e
