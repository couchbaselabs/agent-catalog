import abc
import datetime
import logging
import typing
import uuid

from ...analytics import Kind
from ...analytics import Log
from ...version import VersionDescriptor
from ..scope import Scope

logger = logging.getLogger(__name__)


class BaseLogger(abc.ABC):
    def __init__(self, catalog_version: VersionDescriptor, **kwargs):
        self.catalog_version = catalog_version
        self.annotations = kwargs

    def log(
        self,
        kind: Kind,
        scope: Scope,
        content: typing.Any,
        identifier: typing.AnyStr = None,
        timestamp: datetime.datetime = None,
        **kwargs,
    ):
        # If the timestamp is not given, generate this value ourselves.
        if timestamp is None:
            timestamp = datetime.datetime.now().astimezone()

        message = Log(
            identifier=identifier or uuid.uuid4().hex,
            timestamp=timestamp.isoformat(),
            scope=scope.identifier,
            kind=kind,
            content=content,
            catalog_version=self.catalog_version,
            # Note: The accept call annotations take precedence over init-time annotations.
            annotations={**self.annotations, **kwargs},
        )
        self._accept(message)

        # For debug, we'll pretty-print what we log.
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Logging message: {message.model_dump_json(indent=2)}")

    @abc.abstractmethod
    def _accept(self, message: Log):
        pass
