import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import datetime
import json
import logging

from ...analytics import Log
from ...analytics.create import create_analytics_udfs
from ...defaults import DEFAULT_AUDIT_COLLECTION
from ...defaults import DEFAULT_AUDIT_SCOPE
from ...version import VersionDescriptor
from .base import BaseAuditor
from agentc_core.util.connection import get_host_name
from agentc_core.util.models import CouchbaseConnect
from agentc_core.util.publish import create_scope_and_collection

logger = logging.getLogger(__name__)


class DBAuditor(BaseAuditor):
    def __init__(
        self,
        conn_string: str,
        username: str,
        password: str,
        certificate: str | None,
        bucket: str,
        catalog_version: VersionDescriptor,
        model_name: str,
        agent_name: str,
    ):
        super().__init__(catalog_version, model_name, agent_name)

        # (this is to validate our connection parameters).
        CouchbaseConnect(
            connection_url=conn_string,
            username=username,
            password=password,
            host=get_host_name(conn_string),
            certificate=certificate,
        )

        # All exceptions should be raised if we cannot connect.
        auth = (
            couchbase.auth.PasswordAuthenticator(username, password)
            if certificate is None
            else couchbase.auth.PasswordAuthenticator(username, password, cert_path=certificate)
        )
        options = couchbase.options.ClusterOptions(auth)
        logger.debug(f"Connecting to Couchbase cluster at {conn_string}...")
        cluster = couchbase.cluster.Cluster(conn_string, options)
        cluster.wait_until_ready(datetime.timedelta(seconds=10))
        logger.debug("Connection successfully established.")

        # Get bucket ref
        cb = cluster.bucket(bucket)

        # Get the bucket manager
        bucket_manager = cb.collections()
        msg, err = create_scope_and_collection(bucket_manager, DEFAULT_AUDIT_SCOPE, DEFAULT_AUDIT_COLLECTION)
        if err is not None:
            logger.error(err)
            raise err

        try:
            create_analytics_udfs(cluster, bucket)
        except couchbase.exceptions.CouchbaseException as e:
            logger.warning("Analytics views could not be created: %s", e)
            pass

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
