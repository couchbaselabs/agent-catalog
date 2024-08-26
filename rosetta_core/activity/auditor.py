import logging
import typing

from ..llm import Message
from ..llm import Role
from ..version import VersionDescriptor

logger = logging.getLogger(__name__)


class Auditor:
    def __init__(self, catalog_version: VersionDescriptor, output: typing.TextIO, model: str = None):
        """
        :param catalog_version: Catalog version associated with this audit instance.
        :param output: Output file to write results to.
        :param model: LLM model used with this audit instance. This field can be specified on instantiation
                      or on accept(). A model specified in accept() overrides a model specified on instantiation.
        """
        self.catalog_version = catalog_version
        self.output = output
        self.model = model

    def accept(self, role: Role, content: typing.AnyStr, model: str = None):
        if self.model is None and model is None:
            raise ValueError('"model" must be specified either in accept() or on instantiation!')
        message = Message(role=role, content=content, model=model or self.model, catalog_version=self.catalog_version)
        self.output.write(message.model_dump_json())
        if logger.isEnabledFor(logging.DEBUG):
            # For debug, we'll pretty-print what we log.
            logger.debug(f"Logging message: {message.model_dump_json(indent=2)}")

    def close(self):
        self.output.flush()
        self.output.close()
        logger.info("Auditor has been closed. Output has been written to disk.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
