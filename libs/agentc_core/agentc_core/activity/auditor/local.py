import gzip
import logging
import logging.handlers
import os
import pathlib
import shutil

from ...analytics import Log
from ...version import VersionDescriptor
from .base import BaseAuditor

logger = logging.getLogger(__name__)


class LocalAuditor(BaseAuditor):
    def __init__(
        self,
        output: pathlib.Path,
        catalog_version: VersionDescriptor,
        rollover: int = 128_000_000,
        model_name: str = None,
        agent_name: str = None,
    ):
        """
        :param output: Output file to write the audit logs to.
        :param catalog_version: Catalog version associated with this audit instance.
        :param rollover: Maximum size (bytes) of a log-file before rollover. Set this field to 0 to never rollover.
        :param model_name: LLM model used with this audit instance. This field can be specified on instantiation
               or on accept(). A model_name specified in accept() overrides a model specified on instantiation.
        :param agent_name: Agent name used with this audit instance. This field can be specified on instantiation
               or on accept(). An agent_name specified in accept() overrides a model specified on instantiation.
        """
        super(LocalAuditor, self).__init__(
            model_name=model_name, catalog_version=catalog_version, agent_name=agent_name
        )
        self.audit_logger = logging.getLogger("AGENT_CATALOG_" + LocalAuditor.__name__.upper())
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.handlers.clear()
        self.audit_logger.propagate = False

        def compress_and_remove(source_log_file: str, dest_log_file: str):
            with open(source_log_file, "rb") as input_fp, gzip.open(dest_log_file, "wb") as output_fp:
                shutil.copyfileobj(input_fp, output_fp)
            os.remove(source_log_file)

        # We'll rotate log files and subsequently compress them when they get too large.
        rotating_handler = logging.handlers.RotatingFileHandler(output, maxBytes=rollover)
        rotating_handler.rotator = compress_and_remove
        rotating_handler.namer = lambda name: name + ".gz"
        rotating_handler.setFormatter(logging.Formatter("%(message)s"))
        self.audit_logger.addHandler(rotating_handler)

    def _accept(self, message: Log):
        self.audit_logger.info(message.model_dump_json())
