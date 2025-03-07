import logging
import textwrap

from ...defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from ...defaults import DEFAULT_ACTIVITY_SCOPE
from .base import BaseLogger
from agentc_core.activity.models.log import Log
from agentc_core.config import RemoteCatalogConfig
from agentc_core.remote.util.ddl import check_if_scope_collection_exist
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
            bucket_manager, DEFAULT_ACTIVITY_SCOPE, DEFAULT_ACTIVITY_LOG_COLLECTION, False
        )
        if not scope_collection_exist:
            raise ValueError(
                textwrap.dedent(f"""
                The collection {cfg.bucket}.{DEFAULT_ACTIVITY_SCOPE}.{DEFAULT_ACTIVITY_LOG_COLLECTION} does not exist.\n
                Please use the 'agentc init' command to create this collection.\n
                Execute 'agentc init --help' for more information.
            """)
            )

        # get collection ref
        cb_coll = cb.scope(DEFAULT_ACTIVITY_SCOPE).collection(DEFAULT_ACTIVITY_LOG_COLLECTION)
        self.cb_coll = cb_coll

    def _accept(self, log_obj: Log, log_json: dict):
        self.cb_coll.insert(log_obj.identifier, log_json)
