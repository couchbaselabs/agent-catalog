import couchbase.exceptions
import functools
import logging
import pydantic
import textwrap
import typing
import uuid

from .logger import ChainLogger
from .logger import DBLogger
from .logger import LocalLogger
from agentc_core.activity.models.content import BeginContent
from agentc_core.activity.models.content import Content
from agentc_core.activity.models.content import EndContent
from agentc_core.activity.models.content import KeyValueContent
from agentc_core.activity.models.log import Log
from agentc_core.config import LocalCatalogConfig
from agentc_core.config import RemoteCatalogConfig
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


class Span(pydantic.BaseModel):
    class Identifier(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(frozen=True)
        name: list[str]
        session: str

    logger: typing.Callable[..., Log]
    """ Method which handles the logging implementation. """

    name: str
    """ Name to bind to each message logged within this span. """

    parent: "Span" = None
    """ Parent span of this span (i.e., the span that had :py:meth:`new` called on it). """

    state: typing.Any = None
    """ A JSON-serializable object that will be logged on entering and exiting this span. """

    iterable: typing.Optional[bool] = False
    """ Flag to indicate whether or not this span should be iterable. """

    kwargs: typing.Optional[dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    """ Annotations to apply to all messages logged within this span. """

    _logs: list[Log] = None

    @pydantic.model_validator(mode="after")
    def _initialize_iterable_logger(self) -> typing.Self:
        if self.iterable:
            logger.debug(f"Iterable span requested for {str(self.identifier.name)}.")
            self._logs = list()

            # The logs captured here belong to this specific span (i.e., "iterable" is not propagated to children).
            original_logger = self.logger

            @functools.wraps(original_logger)
            def iterable_logger(*args, **kwargs) -> typing.Callable[..., Log]:
                log = original_logger(*args, **kwargs)
                self._logs.append(log)
                return log

            self.logger = iterable_logger

        return self

    def new(self, name: str, state: typing.Any = None, iterable: bool = False, **kwargs) -> "Span":
        new_kwargs = {**self.kwargs, **kwargs}
        return Span(
            logger=self.logger,
            name=name,
            parent=self,
            iterable=iterable,
            state=state or self.state,
            kwargs=new_kwargs,
        )

    def log(self, content: Content, **kwargs):
        new_kwargs = {**self.kwargs, **kwargs}
        identifier: Span.Identifier = self.identifier
        _log = self.logger(content=content, session_id=identifier.session, span_name=identifier.name, **new_kwargs)
        if self.iterable:
            self._logs.append(_log)

    @pydantic.computed_field
    @property
    def identifier(self) -> "Span.Identifier":
        name_stack = [self.name]
        working = self
        while working.parent is not None:
            name_stack += [working.parent.name]
            working = working.parent
        return Span.Identifier(name=list(reversed(name_stack)), session=working.session)

    def enter(self) -> typing.Self:
        self.log(content=BeginContent() if self.state is None else BeginContent(state=self.state))
        return self

    def exit(self):
        self.log(content=EndContent() if self.state is None else EndContent(state=self.state))

    def logs(self) -> typing.Iterable[Log]:
        if not self.iterable:
            raise ValueError("This span is not iterable. To iterate over logs, set 'iterable'=True on instantiation.")
        return self._logs

    def __enter__(self):
        return self.enter()

    def __setitem__(self, key: str, value: typing.Any):
        self.log(content=KeyValueContent(key=key, value=value))

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We will only record this transition if we are exiting cleanly.
        if all(x is None for x in [exc_type, exc_val, exc_tb]):
            self.exit()

    def __iter__(self):
        if not self.iterable:
            raise ValueError("This span is not iterable. To iterate over logs, set 'iterable'=True on instantiation.")
        yield from self._logs


class GlobalSpan(Span):
    """An auditor of various events (e.g., LLM completions) given a catalog."""

    # Note: this is more of a composite type rather than a union type.
    config: typing.Union[LocalCatalogConfig, RemoteCatalogConfig]
    """ Config (configuration) instance associated with this activity. """

    session: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex, frozen=True)
    """ The run (alternative: session) that this span is associated with. """

    version: VersionDescriptor = pydantic.Field(frozen=True)
    """ Catalog version to bind all messages logged within this auditor. """

    logger: typing.Optional[typing.Callable] = None
    _local_logger: LocalLogger = None
    _db_logger: DBLogger = None
    _chain_logger: ChainLogger = None

    @pydantic.model_validator(mode="after")
    def _find_local_activity(self) -> typing.Self:
        if self.config.activity_path is None:
            try:
                # Note: this method sets the self.config.activity_path attribute if found.
                self.config.ActivityPath()
            except ValueError as e:
                logger.debug(
                    f"Local activity (folder) not found while trying to initialize a Span instance. "
                    f"Swallowing exception {str(e)}."
                )
        return self

    @pydantic.model_validator(mode="after")
    def _initialize_auditor(self) -> typing.Self:
        if self.config.activity_path is None and self.config.conn_string is None:
            error_message = textwrap.dedent("""
                Could not initialize a local or remote auditor!
                If this is a new project, please run the command `agentc init` before instantiating an auditor.
                If you are intending to use a remote-only auditor, please ensure that all of the relevant variables
                (i.e., conn_string, username, password, and bucket) are set.
            """)
            logger.error(error_message)
            raise ValueError(error_message)

        # Finally, instantiate our auditors.
        if self.config.activity_path is not None:
            self._local_logger = LocalLogger(cfg=self.config, catalog_version=self.version, **self.kwargs)
        if self.config.conn_string is not None:
            try:
                self._db_logger = DBLogger(cfg=self.config, catalog_version=self.version, **self.kwargs)
            except (couchbase.exceptions.CouchbaseException, ValueError) as e:
                logger.warning(
                    f"Could not connect to the Couchbase cluster. "
                    f"Skipping remote auditor and swallowing exception {str(e)}."
                )
                self._db_logger = None

        # If we have both a local and remote auditor, we'll use both.
        if self._local_logger is not None and self._db_logger is not None:
            logger.info("Using both a local auditor and a remote auditor.")
            self._chain_logger = ChainLogger(self._local_logger, self._db_logger, **self.kwargs)
            self.logger = self._chain_logger.log
        elif self._local_logger is not None:
            logger.info("Using a local auditor (a connection to a remote auditor could not be established).")
            self.logger = self._local_logger.log
        elif self._db_logger is not None:
            logger.info("Using a remote auditor (a local auditor could not be instantiated).")
            self.logger = self._db_logger.log
        else:
            # We should never reach this point (this error is handled above).
            raise ValueError("Could not instantiate an auditor.")
        return self

    def new(self, name: str, state: typing.Any = None, iterable: bool = False, **kwargs) -> Span:
        """Create a new span under the current activity.

        :param name: The name of the span.
        :param state: The starting state of the span. This will be recorded upon entering and exiting the span.
        :param iterable: Whether or not this new span should be iterable.
        :param kwargs: Additional annotations to apply to the span.
        """
        return Span(logger=self.logger, name=name, parent=self, state=state, iterable=iterable, kwargs=kwargs)
