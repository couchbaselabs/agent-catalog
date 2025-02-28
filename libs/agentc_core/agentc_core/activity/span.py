import couchbase.exceptions
import logging
import pydantic
import textwrap
import typing
import uuid

from ..analytics import CustomContent
from ..analytics import Kind
from ..analytics import TransitionContent
from .logger import DBLogger
from .logger import LocalLogger
from agentc_core.config import LocalCatalogConfig
from agentc_core.config import RemoteCatalogConfig
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


class Span(pydantic.BaseModel):
    class Identifier(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(frozen=True)
        name: list[str]
        session: str

    logger: typing.Optional[typing.Callable] = None
    """ Method which handles the logging implementation. """

    name: str
    """ Name to bind to each message logged within this span. """

    parent: "Span" = None
    """ Parent span of this span (i.e., the span that had :py:meth:`new` called on it). """

    state: typing.Any = None
    """ A JSON-serializable object that will be logged on entering and exiting this span. """

    kwargs: typing.Optional[dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    """ Annotations to apply to all messages logged within this span. """

    def new(self, name: typing.AnyStr, state: typing.Any = None, **kwargs):
        new_kwargs = {**self.kwargs, **kwargs}
        return Span(
            logger=self.logger,
            name=name,
            parent=self,
            state=state or self.state,
            kwargs=new_kwargs,
        )

    def log(self, kind: Kind, content: typing.Any, **kwargs):
        new_kwargs = {**self.kwargs, **kwargs}
        identifier: Span.Identifier = self.identifier
        self.logger(kind=kind, content=content, session_id=identifier.session, span_name=identifier.name, **new_kwargs)

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
        self.log(
            kind=Kind.Transition,
            content=TransitionContent(to_state=self.state or self.identifier, from_state=None, extra=None),
        )
        return self

    def exit(self):
        self.log(
            kind=Kind.Transition,
            content=TransitionContent(to_state=None, from_state=self.state or self.identifier, extra=None),
        )

    def __enter__(self):
        return self.enter()

    def __setitem__(self, key, value):
        self.log(kind=Kind.Custom, content=CustomContent(name=key, value=value, extra=self.kwargs))

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We will only record this transition if we are exiting cleanly.
        if all(x is None for x in [exc_type, exc_val, exc_tb]):
            self.exit()


class GlobalSpan(Span):
    """An auditor of various events (e.g., LLM completions) given a catalog."""

    # Note: this is more of a composite type rather than a union type.
    config: typing.Union[LocalCatalogConfig, RemoteCatalogConfig]
    """ Config (configuration) instance associated with this activity. """

    session: typing.AnyStr = pydantic.Field(default_factory=lambda: uuid.uuid4().hex, frozen=True)
    """ The run (alternative: session) that this span is associated with. """

    version: VersionDescriptor = pydantic.Field(frozen=True)
    """ Catalog version to bind all messages logged within this auditor. """

    _local_logger: LocalLogger = None
    _db_logger: DBLogger = None

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
            self._local_logger = LocalLogger(cfg=self.config, catalog_version=self.version)
        if self.config.conn_string is not None:
            try:
                self._db_logger = DBLogger(cfg=self.config, catalog_version=self.version)
            except (couchbase.exceptions.CouchbaseException, ValueError) as e:
                logger.warning(
                    f"Could not connect to the Couchbase cluster. "
                    f"Skipping remote auditor and swallowing exception {str(e)}."
                )
                self._db_logger = None

        # If we have both a local and remote auditor, we'll use both.
        if self._local_logger is not None and self._db_logger is not None:
            logger.info("Using both a local auditor and a remote auditor.")

            def accept(*args, **kwargs):
                self._local_logger.log(*args, **kwargs)
                self._db_logger.log(*args, **kwargs)

            self.logger = accept
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

    def new(self, name: typing.AnyStr, state: typing.Any = None, **kwargs) -> Span:
        """Create a new span under the current activity.

        :param name: The name of the span.
        :param state: The starting state of the span. This will be recorded upon entering and exiting the span.
        :param kwargs: Additional annotations to apply to the span.
        """
        return Span(logger=self.logger, name=name, parent=self, state=state, kwargs=kwargs)
