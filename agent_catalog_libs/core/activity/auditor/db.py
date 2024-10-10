import json
import logging

from ...analytics import Log
from ...analytics.create import create_analytics_views
from ...defaults import DEFAULT_AUDIT_COLLECTION
from ...defaults import DEFAULT_AUDIT_SCOPE
from ...version import VersionDescriptor
from .base import BaseAuditor
from agent_catalog_libs.util.connection import get_host_name
from agent_catalog_libs.util.models import CouchbaseConnect
from agent_catalog_libs.util.publish import create_scope_and_collection
from agent_catalog_libs.util.publish import get_connection

logger = logging.getLogger(__name__)


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

        create_analytics_views(cluster, bucket)

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
