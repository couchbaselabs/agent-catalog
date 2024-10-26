import abc
import datetime
import logging
import typing

from ...analytics import Kind
from ...analytics import Log
from ...version import VersionDescriptor

logger = logging.getLogger(__name__)


# We have this signature / prototype so the agentc repo can mock a BaseAuditor instance w/o implementing _accept.
class AuditorType(typing.Protocol):
    def accept(
        self,
        kind: Kind,
        content: typing.Any,
        session: typing.AnyStr,
        grouping: typing.AnyStr = None,
        timestamp: datetime.datetime = None,
        model_name: str = None,
        agent_name: str = None,
        **kwargs,
    ) -> None: ...


class BaseAuditor(abc.ABC):
    def __init__(self, catalog_version: VersionDescriptor, model_name: str = None, agent_name: str = None):
        self.catalog_version = catalog_version
        self.model_name = model_name
        self.agent_name = agent_name

    def accept(
        self,
        kind: Kind,
        content: typing.Any,
        session: typing.AnyStr,
        grouping: typing.AnyStr = None,
        timestamp: datetime.datetime = None,
        model_name: str = None,
        agent_name: str = None,
        **kwargs,
    ):
        # If the timestamp is not given, generate this value ourselves.
        if timestamp is None:
            timestamp = datetime.datetime.now().astimezone()

        message = Log(
            timestamp=timestamp.isoformat(),
            session=session,
            kind=kind,
            content=content,
            grouping=grouping,
            catalog_version=self.catalog_version,
            annotations=kwargs,
            llm_model_name=model_name or self.model_name,
            agent_name=agent_name or self.agent_name,
        )
        self._accept(message)

        # For debug, we'll pretty-print what we log.
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Logging message: {message.model_dump_json(indent=2)}")

    @abc.abstractmethod
    def _accept(self, message: Log):
        pass
