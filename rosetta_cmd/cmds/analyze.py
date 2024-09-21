import couchbase.cluster
import typing

from ..models import CouchbaseConnect
from ..models import Keyspace
from ..models.context import Context


def cmd_analyze(
    ctx: Context,
    cluster: couchbase.cluster.Cluster,
    keyspace: Keyspace,
    conn_details: CouchbaseConnect,
    printer: typing.Callable[..., None],
):
    pass
