import datetime
import logging
import pathlib
import pydantic
import pydantic_settings
import rosetta_cmd.defaults
import rosetta_core.activity
import rosetta_core.llm
import textwrap
import typing

from .provider import Provider

logger = logging.getLogger(__name__)

# On audits, we need to export the "role" associated with a message.
Role = rosetta_core.llm.message.Role


class Auditor(pydantic_settings.BaseSettings):
    """An auditor of various events (e.g., LLM completions) given a Rosetta catalog."""

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="ROSETTA_", use_attribute_docstrings=True)

    llm_name: str = None
    """ Name of the LLM model used to generate the chat messages to-be-audited.

    This field can be specified on instantiation or on accept(). A model specified in accept() overrides a model
    specified on instantiation.
    """

    conn_string: typing.Optional[str] = None
    """ Couchbase connection string that points to the Rosetta audit logs.

    This Couchbase instance refers to a CB instance that possesses the audit log collection. This collection is
    automatically generated on `rosetta index`, so this field is most likely the same instance as the CB instance
    possessing the catalog. If there exists no local audit log location (e.g., this is deployed in a standalone
    environment) OR if $ROSETTA_CATALOG is not explicitly set, we will perform all "accept" commands directly on the
    remote audit log collection.

    This field must be specified with username, password, and bucket.
    """

    username: typing.Optional[pydantic.SecretStr] = None
    """ Username associated with the Couchbase instance possessing the Rosetta audit logs.

    This field must be specified with conn_string, password, and bucket.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance possessing the Rosetta audit logs.

    This field must be specified with conn_string, username, and bucket.
    """

    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket possessing the Rosetta audit logs.

    This field must be specified with conn_string, username, and password.
    """

    catalog: typing.Optional[pathlib.Path] = None
    """ Location of the catalog path.

    This field is used to search for the catalog version. If this field is not set, we will defer to the default
    behavior of rosetta.Provider.
    """

    local_log: typing.Optional[pathlib.Path] = None
    """ Local audit log file to write to.

    If this field and $ROSETTA_CONN_STRING are not set, we will perform a best-effort search by walking upward from the
    current working directory until we find the 'rosetta.cmd.defaults.DEFAULT_ACTIVITY_FOLDER' folder and subsequently
    generate an audit log here.

    Audit log files will reach a maximum of 128MB (by default) before they are rotated and compressed.
    """

    _local_auditor: rosetta_core.activity.LocalAuditor = None
    _db_auditor: rosetta_core.activity.DBAuditor = None
    _auditor: rosetta_core.activity.BaseAuditor = None

    @pydantic.model_validator(mode="after")
    def _find_local_log(self) -> typing.Self:
        if self.local_log is None:
            working_path = pathlib.Path.cwd()
            logger.debug(
                'Starting best effort search for the activity folder. Searching for "%s".',
                rosetta_cmd.defaults.DEFAULT_ACTIVITY_FOLDER,
            )

            # Iteratively ascend our starting path until we find the activity folder.
            while not (working_path / rosetta_cmd.defaults.DEFAULT_ACTIVITY_FOLDER).exists():
                if working_path.parent == working_path:
                    return self
                working_path = working_path.parent
            self.local_log = (
                working_path
                / rosetta_cmd.defaults.DEFAULT_ACTIVITY_FOLDER
                / rosetta_cmd.defaults.DEFAULT_LLM_ACTIVITY_NAME
            )

        return self

    @pydantic.model_validator(mode="after")
    def _find_remote_log(self) -> typing.Self:
        if self.conn_string is None:
            return self

        # Make sure we have {username, password, bucket}.
        if self.username is None:
            logger.warning("$ROSETTA_CONN_STRING is specified but $ROSETTA_USERNAME is missing.")
            return self
        if self.password is None:
            logger.warning("$ROSETTA_CONN_STRING is specified but $ROSETTA_PASSWORD is missing.")
            return self
        if self.bucket is None:
            logger.warning("$ROSETTA_CONN_STRING is specified but $ROSETTA_BUCKET is missing.")
            return self

        return self

    @pydantic.model_validator(mode="after")
    def _initialize_auditor(self) -> typing.Self:
        if self.local_log is None and self.conn_string is None:
            error_message = textwrap.dedent("""
                Could not find $ROSETTA_ACTIVITY nor $ROSETTA_CONN_STRING! If this is a new project, please run the
                command `rosetta index` before instantiating an auditor. Otherwise, please set either of these
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
        if self.local_log is not None:
            self._local_auditor = rosetta_core.activity.LocalAuditor(
                output=self.local_log, catalog_version=provider.version, model=self.llm_name
            )
        if self.conn_string is not None:
            self._db_auditor = rosetta_core.activity.DBAuditor(
                conn_string=self.conn_string,
                username=self.username.get_secret_value(),
                password=self.password.get_secret_value(),
                model=self.llm_name,
                bucket=self.bucket,
                catalog_version=provider.version,
            )
        return self

    def accept(
        self,
        role: Role,
        content: typing.AnyStr,
        session: typing.AnyStr,
        timestamp: datetime.datetime = None,
        model: str = None,
    ) -> None:
        """
        :param role: Role associated with the message. See rosetta_core.llm.message.Role for all options here.
        :param content: The message to record. Ideally, the content should be as close to the producer as possible.
        :param session: A unique string associated with the current session / conversation / thread.
        :param timestamp: The time associated with the message production. This must have time-zone information.
        :param model: LLM model used with this audit instance. This field can be specified on instantiation
                      or on accept(). A model specified in accept() overrides a model specified on instantiation.
        """
        if self._local_auditor is not None:
            self._local_auditor.accept(role, content, session, timestamp=timestamp, model=model or self.llm_name)
        if self._db_auditor is not None:
            self._db_auditor.accept(role, content, session, timestamp=timestamp, model=model or self.llm_name)
