import typing

from couchbase.exceptions import CouchbaseException
from couchbase.options import QueryOptions


def quote_sql_identifier(identifier: str) -> str:
    """Return a safely quoted SQL++ identifier."""

    if not isinstance(identifier, str) or identifier == "":
        raise ValueError("SQL identifier must be a non-empty string.")

    # Escape embedded backticks so the identifier cannot terminate early.
    return f"`{identifier.replace('`', '``')}`"


def quote_sql_keyspace(*parts: str) -> str:
    """Return a dot-separated, safely quoted SQL++ keyspace name."""

    if len(parts) == 0:
        raise ValueError("At least one identifier part is required.")

    return ".".join(quote_sql_identifier(part) for part in parts)


def execute_query(cluster, exec_query) -> tuple[typing.Any, Exception | None]:
    """Execute a given query"""

    try:
        # TODO (GLENN): Why are we catching an exception here? (we should catch exceptions on execute())
        result = cluster.query(exec_query, QueryOptions(metrics=True))
        return result, None
    except CouchbaseException as e:
        return None, e


def execute_query_with_parameters(cluster, exec_query, params) -> tuple[typing.Any, Exception | None]:
    """Execute a given query with given named parameters"""

    try:
        result = cluster.query(exec_query, QueryOptions(metrics=True, named_parameters=params))
        return result, None
    except CouchbaseException as e:
        return None, e
