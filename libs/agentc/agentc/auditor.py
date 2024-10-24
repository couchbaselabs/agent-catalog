import datetime
import logging
import pathlib
import pydantic
import pydantic_settings
import textwrap
import typing

from .provider import Provider
from agentc_core.activity import DBAuditor
from agentc_core.activity import LocalAuditor
from agentc_core.analytics import Kind
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_LLM_ACTIVITY_NAME

logger = logging.getLogger(__name__)

# On audits, we need to export the "kind" associated with a log...
Kind = Kind


class Auditor(pydantic_settings.BaseSettings):
    """An auditor of various events (e.g., LLM completions) given a catalog."""

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    llm_name: str = None
    """ Name of the LLM model used to generate the chat messages to-be-audited.

    This field can be specified on instantiation or on :py:meth:`accept()`.
    A model specified in :py:meth:`accept()` overrides a model specified on instantiation.
    """

    conn_string: typing.Optional[str] = None
    """ Couchbase connection string that points to the audit logs.

    This Couchbase instance refers to a CB instance that possesses the audit log collection.
    This collection is automatically generated on :command:`agentc index`, so this field is most likely the same
    instance as the CB instance possessing the catalog.
    If there exists no local audit log location (e.g., this is deployed in a standalone environment) OR if
    ``$AGENT_CATALOG_CATALOG`` is not explicitly set, we will perform all :py:meth:`accept` commands directly on
    the remote audit log collection.

    This field **must** be specified with :py:attr:`username`, :py:attr:`password`, and  :py:attr:`bucket`.
    """

    username: typing.Optional[pydantic.SecretStr] = None
    """ Username associated with the Couchbase instance possessing the audit logs.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`password`, and :py:attr:`bucket`.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance possessing the audit logs.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`bucket`.
    """

    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket possessing the audit logs.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`password`.
    """

    catalog: typing.Optional[pathlib.Path] = None
    """ Location of the catalog path.

    This field is used to search for the catalog version.
    If this field is not set, we will defer to the default behavior of :py:class:`agentc.Provider`.
    """

    auditor_output: typing.Optional[pathlib.Path] = None
    """ Local audit log file to write to.

    If this field and ``$AGENT_CATALOG_CONN_STRING`` are not set, we will perform a best-effort search by walking upward
    from the current working directory until we find the :py:data:`agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER` folder
    and subsequently generate an audit log here.

    Audit log files will reach a maximum of 128MB (by default) before they are rotated and compressed.
    """

    agent_name: typing.Optional[str] = None
    """ Name of the agent for which this auditor was instantiated.

    This helps user to know query logs by Agent Name
    This field can be specified on instantiation or on :py:meth:`accept()`.
    Agent name specified in :py:meth:`accept()` overrides a model specified on instantiation.
    """

    _local_auditor: LocalAuditor = None
    _db_auditor: DBAuditor = None
    _audit: typing.Callable = None

    @pydantic.model_validator(mode="after")
    def _find_local_log(self) -> typing.Self:
        if self.auditor_output is None:
            working_path = pathlib.Path.cwd()
            logger.debug(
                'Starting best effort search for the activity folder. Searching for "%s".',
                DEFAULT_ACTIVITY_FOLDER,
            )

            # Iteratively ascend our starting path until we find the activity folder.
            while not (working_path / DEFAULT_ACTIVITY_FOLDER).exists():
                if working_path.parent == working_path:
                    return self
                working_path = working_path.parent
            self.auditor_output = working_path / DEFAULT_ACTIVITY_FOLDER / DEFAULT_LLM_ACTIVITY_NAME

        return self

    @pydantic.model_validator(mode="after")
    def _find_remote_log(self) -> typing.Self:
        if self.conn_string is None:
            return self

        # Make sure we have {username, password, bucket}.
        if self.username is None:
            logger.warning("$AGENT_CATALOG_CONN_STRING is specified but $AGENT_CATALOG_USERNAME is missing.")
            return self
        if self.password is None:
            logger.warning("$AGENT_CATALOG_CONN_STRING is specified but $AGENT_CATALOG_PASSWORD is missing.")
            return self
        if self.bucket is None:
            logger.warning("$AGENT_CATALOG_CONN_STRING is specified but $AGENT_CATALOG_BUCKET is missing.")
            return self

        return self

    @pydantic.model_validator(mode="after")
    def _initialize_auditor(self) -> typing.Self:
        if self.auditor_output is None and self.conn_string is None:
            error_message = textwrap.dedent("""
                Could not find $AGENT_CATALOG_ACTIVITY nor $AGENT_CATALOG_CONN_STRING! If this is a new project, please
                run the command `agentc index` before instantiating an auditor. Otherwise, please set either of these
                variables.
            """)
            logger.error(error_message)
            raise ValueError(error_message)

        # To grab the catalog version, we'll instantiate a provider.
        provider = Provider(
            conn_string=self.conn_string,
            username=self.username,
            password=self.password,
            bucket=self.bucket,
            catalog=self.catalog,
        )

        # Finally, instantiate our auditors.
        if self.auditor_output is not None:
            self._local_auditor = LocalAuditor(
                output=self.auditor_output, catalog_version=provider.version, model=self.llm_name
            )
        if self.conn_string is not None:
            self._db_auditor = DBAuditor(
                conn_string=self.conn_string,
                username=self.username.get_secret_value(),
                password=self.password.get_secret_value(),
                model=self.llm_name,
                bucket=self.bucket,
                catalog_version=provider.version,
            )

        # If we have both a local and remote auditor, we'll use both.
        if self._local_auditor is not None and self._db_auditor is not None:
            logger.info("Using both a local auditor and a remote auditor.")

            def accept(*args, **kwargs):
                self._local_auditor.accept(*args, **kwargs)
                self._db_auditor.accept(*args, **kwargs)

            self._audit = accept
        elif self._local_auditor is not None:
            logger.info("Using a local auditor (a connection to a remote auditor could not be established).")
            self._audit = self._local_auditor.accept
        elif self._db_auditor is not None:
            logger.info("Using a remote auditor (a local auditor could not be instantiated).")
            self._audit = self._db_auditor.accept
        else:
            # We should never reach this point (this error is handled above).
            raise ValueError("Could not instantiate an auditor.")

        return self

    def accept(
        self,
        kind: Kind,
        content: typing.Any,
        session: typing.AnyStr,
        grouping: typing.AnyStr = None,
        timestamp: datetime.datetime = None,
        model: str = None,
        agent_name: str = None,
        **kwargs,
    ) -> None:
        """
        :param kind: Kind associated with the message. See analytics.log.Kind for all options here.
        :param content: The (JSON-serializable) message to record. This should be as close to the producer as possible.
        :param session: A unique string associated with the current session / conversation / thread.
        :param grouping: A unique string associated with one "generate" invocation across a group of messages.
        :param timestamp: The time associated with the message production. This must have time-zone information.
        :param model: LLM model used with this audit instance. This field can be specified on instantiation
                      or on accept(). A model specified in accept() overrides a model specified on instantiation.
        :param agent_name: Name of the Agent associated with this audit instance.
        """
        model = model if model is not None else self.llm_name
        agent_name = agent_name if agent_name is not None else self.agent_name

        self._audit(
            kind=kind,
            content=content,
            session=session,
            grouping=grouping,
            timestamp=timestamp,
            model=model,
            agent_name=agent_name,
            **kwargs,
        )

    def move(
        self,
        node_name: typing.AnyStr,
        direction: typing.Literal["enter", "exit"],
        session: typing.AnyStr,
        content: typing.Any = None,
        timestamp: datetime.datetime = None,
        model: str = None,
        agent_name: str = None,
        **kwargs,
    ):
        """
        :param node_name: The node / state this message applies to.
        :param direction: The direction of the move. This can be either "enter" or "exit".
        :param session: A unique string associated with the current session / conversation / thread.
        :param content: Any additional content that should be recorded with this message.
        :param timestamp: The time associated with the message production. This must have time-zone information.
        :param model: LLM model used with this audit instance. This field can be specified on instantiation
                      or on enter(). A model specified in enter() overrides a model specified on instantiation.
        :param agent_name: Name of the Agent associated with this audit instance.
        """
        model = model if model is not None else self.llm_name
        agent_name = agent_name if agent_name is not None else self.agent_name

        if direction == "enter":
            content = dict(to_node=node_name, extra=content)
        elif direction == "exit":
            content = dict(from_node=node_name, extra=content)
        else:
            raise ValueError('Direction must be either "enter" or "exit".')

        self._audit(
            kind=Kind.Transition,
            content=content,
            session=session,
            timestamp=timestamp,
            model=model,
            agent_name=agent_name,
            **kwargs,
        )
