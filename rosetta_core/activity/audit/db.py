import logging

from ...defaults import DEFAULT_AUDIT_COLLECTION
from ...defaults import DEFAULT_AUDIT_SCOPE
from ...llm import Message
from ...version import VersionDescriptor
from .base import BaseAuditor
from rosetta_cmd.models import CouchbaseConnect
from rosetta_util.publish import create_scope_and_collection
from rosetta_util.publish import get_connection

logger = logging.getLogger(__name__)


# TODO (GLENN): Implement this.
class DBAuditor(BaseAuditor):
    def __init__(self, bucket: str, secrets: dict, catalog_version: VersionDescriptor, model: str):
        super().__init__(catalog_version, model)
        self.secrets = secrets
        conn = CouchbaseConnect(
            connection_url=self.secrets["CB_CONN_STRING"],
            username=self.secrets["CB_USERNAME"],
            password=self.secrets["CB_PASSWORD"],
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

    def _accept(self, message: Message):
        cb_coll = self.cb_coll

        # serialise message object to str
        message_json = message.model_dump_json()
        try:
            key = message.timestamp
            # upsert docs to CB collection
            cb_coll.upsert(key, message_json)
        except Exception as e:
            logger.error("could not insert log: ", e)

        return

    def close(self):
        self.cluster.close()
        return

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
