import json
import logging
import textwrap

from ...analytics import Log
from ...defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from ...defaults import DEFAULT_AUDIT_SCOPE
from ...util.ddl import check_if_scope_collection_exist
from .base import BaseLogger
from agentc_core.config import RemoteCatalogConfig
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


class DBLogger(BaseLogger):
    def __init__(self, cfg: RemoteCatalogConfig, catalog_version: VersionDescriptor, **kwargs):
        super().__init__(catalog_version=catalog_version, **kwargs)

        # Get bucket ref
        self.cluster = cfg.Cluster()
        cb = self.cluster.bucket(cfg.bucket)

        # Get the bucket manager
        bucket_manager = cb.collections()

        scope_collection_exist = check_if_scope_collection_exist(
            bucket_manager, DEFAULT_AUDIT_SCOPE, DEFAULT_ACTIVITY_LOG_COLLECTION, False
        )
        if not scope_collection_exist:
            raise ValueError(
                textwrap.dedent(f"""
                The collection {cfg.bucket}.{DEFAULT_AUDIT_SCOPE}.{DEFAULT_ACTIVITY_LOG_COLLECTION} does not exist.\n
                Please use the 'agentc init' command to create this collection.\n
                Execute 'agentc init --help' for more information.
            """)
            )

        # get collection ref
        cb_coll = cb.scope(DEFAULT_AUDIT_SCOPE).collection(DEFAULT_ACTIVITY_LOG_COLLECTION)
        self.cb_coll = cb_coll

    def _accept(self, message: Log):
        cb_coll = self.cb_coll

        # serialise message object to str
        message_str = message.model_dump_json()
        message_json = json.loads(message_str)

        # upsert docs to CB collection
        key = f"{message.timestamp}/{str(message.scope)}"
        cb_coll.upsert(key, message_json)
