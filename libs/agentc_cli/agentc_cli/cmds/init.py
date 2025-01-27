import typing

from ..models import Context
from .util import init_db_auditor
from .util import init_db_catalog
from .util import init_local_activity
from .util import init_local_catalog
from agentc_core.util.models import CouchbaseConnect
from agentc_core.util.models import Keyspace
from agentc_core.util.publish import get_connection

func_mappings = {"local": {"catalog": init_local_catalog, "auditor": init_local_activity}}


def cmd_init(
    ctx: Context,
    catalog_type: typing.List[typing.Literal["catalog", "auditor"]],
    type_metadata: typing.List[typing.Literal["catalog", "auditor"]],
    connection_details_env: typing.Optional[CouchbaseConnect] = None,
    keyspace_details: typing.Optional[Keyspace] = None,
):
    if ctx is None:
        ctx = Context()
    initialize_local = "local" in catalog_type
    initialize_db = "db" in catalog_type
    initialize_catalog = "catalog" in type_metadata
    initialize_auditor = "auditor" in type_metadata

    if initialize_local:
        if initialize_catalog:
            init_local_catalog(ctx)
        if initialize_auditor:
            init_local_activity(ctx)

    if initialize_db:
        # Get bucket ref
        err, cluster = get_connection(conn=connection_details_env)
        if err:
            raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        if initialize_catalog:
            init_db_catalog(ctx, cluster, keyspace_details, connection_details_env)

        if initialize_auditor:
            init_db_auditor(ctx, cluster, keyspace_details)
