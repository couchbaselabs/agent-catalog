from couchbase.exceptions import CouchbaseException
from couchbase.options import QueryOptions


def execute_query(cluster, exec_query) -> tuple[any, Exception | None]:
    """Execute a given query"""

    try:
        # TODO (GLENN): Why are we catching an exception here? (we should catch exceptions on execute())
        result = cluster.query(exec_query, QueryOptions(metrics=True))
        return result, None
    except CouchbaseException as e:
        return None, e


def execute_query_with_parameters(cluster, exec_query, params) -> tuple[any, Exception | None]:
    """Execute a given query with given named parameters"""

    try:
        result = cluster.query(exec_query, QueryOptions(metrics=True, named_parameters=params))
        return result, None
    except CouchbaseException as e:
        return None, e
