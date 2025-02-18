import couchbase.exceptions
import logging
import pydantic
import textwrap
import typing

from ..analytics import CustomContent
from ..analytics import Kind
from ..analytics import TransitionContent
from .logger import DBLogger
from .logger import LocalLogger
from agentc_core.config import Config

logger = logging.getLogger(__name__)


class Scope:
    def __init__(self, log: typing.Callable, name: str, parent: "Scope" = None, state: typing.Any = None, **kwargs):
        self.log = log
        self.name = name
        self.parent = parent
        self.state = state
        self.kwargs = kwargs

    def new(self, name: typing.AnyStr, state: typing.Any = None, **kwargs):
        new_kwargs = {**self.kwargs, **kwargs}
        return Scope(
            log=self.log,
            name=name,
            parent=self,
            state=state or self.state,
            kwargs=new_kwargs,
        )

    def log(self, kind: Kind, content: typing.Any, **kwargs):
        new_kwargs = {**self.kwargs, **kwargs}
        self.log(kind=kind, content=content, scope=self, **new_kwargs)

    @property
    def identifier(self) -> list[str]:
        name_stack = [self.name]
        parent = self.parent
        while parent is not None:
            name_stack.append(parent.name)
            parent = parent.parent
        return reversed(name_stack)

    def __enter__(self):
        if self.state is not None:
            # We only need to log a transition if state is specified.
            self.log(
                kind=Kind.Transition,
                content=TransitionContent(to_state=self.state, from_state=None, extra=None),
                scope=self,
            )
        return self

    def __setitem__(self, key, value):
        self.log(kind=Kind.Custom, content=CustomContent(name=key, value=value, extra=self.kwargs), scope=self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We will only record this transition if we are exiting cleanly.
        if self.state is not None and all(x is None for x in [exc_type, exc_val, exc_tb]):
            self.log(
                kind=Kind.Transition,
                content=TransitionContent(to_state=None, from_state=self.state, extra=None),
                scope=self,
            )


class GlobalScope(Scope, pydantic.BaseModel):
    """An auditor of various events (e.g., LLM completions) given a catalog."""

    config: Config
    """ Config (configuration) instance associated with this activity.

    This ``config`` instance is used to determine the version of the catalog that this auditor is associated with as
    well as where to write our output to.
    """

    annotations: typing.Optional[dict[str, typing.Any]] = None
    """ Activity-level annotations to apply to all messages.

    These annotations are applied to all messages that are recorded by this auditor.
    To supply annotations to a specific message, use the `annotations` parameter in the `__setitem__` method.
    """

    _local_logger: LocalLogger = None
    _db_logger: DBLogger = None
    _log: typing.Callable = None

    @pydantic.model_validator(mode="after")
    def _find_local_activity(self) -> typing.Self:
        if self.config.activity_path is None:
            try:
                # Note: this method sets the self.config.activity_path attribute if found.
                self.config.ActivityPath()
            except ValueError as e:
                logger.debug(
                    f"Local activity (folder) not found when initializing Scope instance. "
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
            self._local_logger = LocalLogger(cfg=self.config, catalog_version=self.catalog.version)
        if self.conn_string is not None:
            try:
                self._db_logger = DBLogger(cfg=self.config, catalog_version=self.catalog.version)
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

            self._audit = accept
        elif self._local_logger is not None:
            logger.info("Using a local auditor (a connection to a remote auditor could not be established).")
            self._audit = self._local_logger.log
        elif self._db_logger is not None:
            logger.info("Using a remote auditor (a local auditor could not be instantiated).")
            self._audit = self._db_logger.log
        else:
            # We should never reach this point (this error is handled above).
            raise ValueError("Could not instantiate an auditor.")
        return self

    def new(self, name: typing.AnyStr, state: typing.Any = None, **kwargs) -> Scope:
        """Create a new scope under the current activity.

        :param name: The name of the scope.
        :param state: The starting state of the scope. This will be recorded upon entering and exiting the scope.
        :param kwargs: Additional annotations to apply to the scope.
        """
        return Scope(log=self._log, name=name, parent=None, state=state, **kwargs)
