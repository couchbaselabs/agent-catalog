import logging.handlers

from ..models.log import Log
from .base import BaseLogger
from .db import DBLogger
from .local import LocalLogger

logger = logging.getLogger(__name__)


class ChainLogger(BaseLogger):
    # TODO (GLENN): Add rollover to our Config class.
    def __init__(self, local_logger: LocalLogger, db_logger: DBLogger, **kwargs):
        if db_logger.catalog_version != local_logger.catalog_version:
            raise ValueError("Catalog versions must match between remote and local-FS loggers!")
        super(ChainLogger, self).__init__(catalog_version=local_logger.catalog_version, **kwargs)
        self.db_logger = db_logger
        self.local_logger = local_logger

    def _accept(self, log_obj: Log, log_json: dict):
        # We write locally first: the local log is our durable fallback, so a slow or failing cluster must never cost
        # us the on-disk copy of a record.
        self.local_logger._accept(log_obj, log_json)
        self.db_logger._accept(log_obj, log_json)
