import couchbase.exceptions
import couchbase.options
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

        # Grab our TTL for our logs.
        self.ttl = cfg.log_ttl

        # The number of log records we have failed to write to Couchbase (see _accept below).
        self.dropped_log_count = 0

    def _accept(self, log_obj: Log, log_json: dict):
        try:
            self.cb_coll.insert(log_obj.identifier, log_json, couchbase.options.InsertOptions(expiry=self.ttl))
        except couchbase.exceptions.CouchbaseException as e:
            # An agent should never crash because its activity log could not be written. We warn (instead of raising)
            # and continue, mirroring how we handle a cluster that is unreachable at Span-instantiation time.
            self.dropped_log_count += 1
            logger.warning(
                "Could not write the log record %s to Couchbase (%d record(s) dropped for this logger so far). "
                "Swallowing exception %s.",
                log_obj.identifier,
                self.dropped_log_count,
                str(e),
            )
