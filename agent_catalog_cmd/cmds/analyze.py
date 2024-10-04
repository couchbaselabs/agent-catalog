import couchbase.cluster
import typing

from ..models.context import Context
from agent_catalog_util.models import CouchbaseConnect
from agent_catalog_util.models import Keyspace


def cmd_analyze(
    ctx: Context,
    cluster: couchbase.cluster.Cluster,
    keyspace: Keyspace,
    conn_details: CouchbaseConnect,
    printer: typing.Callable[..., None],
):
    pass
