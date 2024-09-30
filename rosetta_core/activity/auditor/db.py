import couchbase.cluster
import json
import logging
import pathlib

from ...analytics import Log
from ...defaults import DEFAULT_AUDIT_COLLECTION
from ...defaults import DEFAULT_AUDIT_SCOPE
from ...version import VersionDescriptor
from .base import BaseAuditor
from rosetta_util.connection import get_host_name
from rosetta_util.models import CouchbaseConnect
from rosetta_util.publish import create_scope_and_collection
from rosetta_util.publish import get_connection

logger = logging.getLogger(__name__)


# TODO (GLENN): This needs to be "plugged in" somewhere (and actually tested :-)).
def _create_analytics_views(cluster: couchbase.cluster.Cluster, bucket: str) -> None:
    ddls_folder = pathlib.Path(__file__).parent / "ddls"
    for ddl_file in ddls_folder.iterdir():
        with open(ddl_file, "r") as fp:
            raw_ddl_string = fp.read()
            ddl_string = (
                raw_ddl_string.replace("[BUCKET_NAME]", bucket)
                .replace("[SCOPE_NAME]", DEFAULT_AUDIT_SCOPE)
                .replace("[LOG_COLLECTION_NAME]", DEFAULT_AUDIT_COLLECTION)
            )

            # TODO (GLENN): There should be a warning here (instead of an error) if Analytics is not enabled.
            ddl_result = cluster.analytics_query(ddl_string)
            for _ in ddl_result.rows():
                pass


class DBAuditor(BaseAuditor):
    def __init__(
        self,
        conn_string: str,
        username: str,
        password: str,
        bucket: str,
        catalog_version: VersionDescriptor,
        model: str,
    ):
        super().__init__(catalog_version, model)
        conn = CouchbaseConnect(
            connection_url=conn_string,
            username=username,
            password=password,
            host=get_host_name(conn_string),
        )
        err, cluster = get_connection(conn)
        if err is not None:
            logger.error(err)
            return

        # Get bucket ref
        cb = cluster.bucket(bucket)

        # Get the bucket manager
        bucket_manager = cb.collections()

        msg, err = create_scope_and_collection(bucket_manager, DEFAULT_AUDIT_SCOPE, DEFAULT_AUDIT_COLLECTION)
        if err is not None:
            logger.error(err)
            return

        # get collection ref
        cb_coll = cb.scope(DEFAULT_AUDIT_SCOPE).collection(DEFAULT_AUDIT_COLLECTION)

        self.cb_coll = cb_coll
        self.cluster = cluster

    def _accept(self, message: Log):
        cb_coll = self.cb_coll

        # serialise message object to str
        message_str = message.model_dump_json()
        message_json = json.loads(message_str)

        # upsert docs to CB collection
        key = message_json["timestamp"] + message_json["session"]
        cb_coll.upsert(key, message_json)
