import couchbase.cluster
import typing

from ..models.context import Context
from rosetta_util.models import CouchbaseConnect
from rosetta_util.models import Keyspace


def cmd_analyze(
    ctx: Context,
    cluster: couchbase.cluster.Cluster,
    keyspace: Keyspace,
    conn_details: CouchbaseConnect,
    printer: typing.Callable[..., None],
):
    pass
