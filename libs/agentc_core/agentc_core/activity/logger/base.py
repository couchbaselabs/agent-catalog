import abc
import datetime
import logging
import uuid

from ...version import VersionDescriptor
from ..models.content import Content
from ..models.log import Log

logger = logging.getLogger(__name__)


class BaseLogger(abc.ABC):
    def __init__(self, catalog_version: VersionDescriptor, **kwargs):
        self.catalog_version = catalog_version
        self.annotations = kwargs

    def log(
        self,
        content: Content,
        span_name: list[str],
        session_id: str,
        log_id: str = None,
        timestamp: datetime.datetime = None,
        **kwargs,
    ) -> Log:
        # If the timestamp is not given, generate this value ourselves.
        if timestamp is None:
            timestamp = datetime.datetime.now().astimezone()

        message = Log(
            identifier=log_id or uuid.uuid4().hex,
            timestamp=timestamp.isoformat(),
            span=Log.Span(name=span_name, session=session_id),
            content=content,
            catalog_version=self.catalog_version,
            # Note: The accept call annotations take precedence over init-time annotations.
            annotations={**self.annotations, **kwargs},
        )
        self._accept(message, message.model_dump(exclude_none=True, mode="json"))

        # For debug, we'll pretty-print what we log.
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Logging message: {message.model_dump_json(indent=2)}")

        return message

    @abc.abstractmethod
    def _accept(self, log_obj: Log, log_json: dict):
        pass
