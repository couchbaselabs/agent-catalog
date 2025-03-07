import agentc_core.defaults
import gzip
import logging
import logging.handlers
import os
import shutil

from ...config import LocalCatalogConfig
from .base import BaseLogger
from agentc_core.activity.models.log import Log
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


class LocalLogger(BaseLogger):
    # TODO (GLENN): Add rollover to our Config class.
    def __init__(
        self, cfg: LocalCatalogConfig, catalog_version: VersionDescriptor, rollover: int = 128_000_000, **kwargs
    ):
        """
        :param output: Output file to write the audit logs to.
        :param catalog_version: Catalog version associated with this audit instance.
        :param rollover: Maximum size (bytes) of a log-file before rollover. Set this field to 0 to never rollover.
        """
        super(LocalLogger, self).__init__(catalog_version=catalog_version, **kwargs)
        self.audit_logger = logging.getLogger("AGENT_CATALOG_" + LocalLogger.__name__.upper())
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.handlers.clear()
        self.audit_logger.propagate = False

        def compress_and_remove(source_log_file: str, dest_log_file: str):
            with open(source_log_file, "rb") as input_fp, gzip.open(dest_log_file, "wb") as output_fp:
                shutil.copyfileobj(input_fp, output_fp)
            os.remove(source_log_file)

        # We'll rotate log files and subsequently compress them when they get too large.
        filename = cfg.ActivityPath() / agentc_core.defaults.DEFAULT_ACTIVITY_FILE
        self.rotating_handler = logging.handlers.RotatingFileHandler(filename, maxBytes=rollover)
        self.rotating_handler.rotator = compress_and_remove
        self.rotating_handler.namer = lambda name: name + ".gz"
        self.rotating_handler.setFormatter(logging.Formatter("%(message)s"))
        self.audit_logger.addHandler(self.rotating_handler)

    def _accept(self, log_obj: Log, log_json: dict):
        self.audit_logger.info(log_json)
