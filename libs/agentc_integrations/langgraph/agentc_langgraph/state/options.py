import acouchbase.cluster
import couchbase.auth
import couchbase.cluster
import couchbase.options
import pathlib
import pydantic
import pydantic_settings
import typing

from agentc_core.config import RemoteCatalogConfig
from agentc_langgraph.defaults import DEFAULT_COUCHBASE_CHECKPOINT_DDL_RETRY_ATTEMPTS
from agentc_langgraph.defaults import DEFAULT_COUCHBASE_CHECKPOINT_DDL_RETRY_WAIT_SECONDS
from agentc_langgraph.defaults import DEFAULT_COUCHBASE_CHECKPOINT_SCOPE_NAME
from agentc_langgraph.defaults import DEFAULT_COUCHBASE_CHECKPOINT_THREAD_COLLECTION_NAME
from agentc_langgraph.defaults import DEFAULT_COUCHBASE_CHECKPOINT_TUPLE_COLLECTION_NAME


class CheckpointOptions(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(
        env_file=".env", env_prefix="AGENT_CATALOG_LANGGRAPH_CHECKPOINT_"
    )

    # Connection-specific details.
    conn_string: typing.Optional[str] = None
    """ The connection string to the Couchbase cluster hosting the cache.

    This field **must** be specified.
    """

    username: typing.Optional[str] = None
    """ Username associated with the Couchbase instance hosting the cache.

    This field **must** be specified.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance hosting the cache.

    This field **must** be specified.
    """

    conn_root_certificate: typing.Optional[str | pathlib.Path] = None
    """ Path to the root certificate file for the Couchbase cluster.

    This field is optional and only required if the Couchbase cluster is using a self-signed certificate.
    """

    # Collection-specific details.
    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket hosting the checkpoints.

    This field **must** be specified.
    """

    scope: typing.Optional[str] = pydantic.Field(default=DEFAULT_COUCHBASE_CHECKPOINT_SCOPE_NAME)
    """ The name of the Couchbase scope hosting the checkpoints.

    This field is optional and defaults to ``agent_activity``.
    """

    checkpoint_collection: typing.Optional[str] = pydantic.Field(
        default=DEFAULT_COUCHBASE_CHECKPOINT_THREAD_COLLECTION_NAME
    )
    """ The name of the Couchbase collection hosting the checkpoints threads.

    This field is optional and defaults to ``langgraph_checkpoint_thread``.
    """

    tuple_collection: typing.Optional[str] = pydantic.Field(default=DEFAULT_COUCHBASE_CHECKPOINT_TUPLE_COLLECTION_NAME)
    """ The name of the Couchbase collection hosting the checkpoints tuples.

    This field is optional and defaults to ``langgraph_checkpoint_tuple``.
    """

    create_if_not_exists: typing.Optional[bool] = False
    """ Create the required collections if they do not exist.

    When raised (i.e., this value is set to :python:`True`), the collections will be created if they do not exist.
    Lower this flag (set this to :python:`False`) to instead raise an error if the collections do not exist.
    """

    ddl_retry_attempts: typing.Optional[int] = DEFAULT_COUCHBASE_CHECKPOINT_DDL_RETRY_ATTEMPTS
    """ Maximum number of attempts to retry DDL operations.

    This value is only used on setup (i.e., the first time the checkpointer is requested).
    If the number of attempts is exceeded, the command will fail.
    By default, this value is 3 attempts.
    """

    ddl_retry_wait_seconds: typing.Optional[float] = DEFAULT_COUCHBASE_CHECKPOINT_DDL_RETRY_WAIT_SECONDS
    """ Wait time (in seconds) between DDL operation retries.

    This value is only used on setup (i.e., the first time the checkpointer is requested).
    By default, this value is 5 seconds.
    """

    @pydantic.model_validator(mode="after")
    def _pull_cluster_from_agent_catalog(self) -> typing.Self:
        config = RemoteCatalogConfig()
        if self.conn_string is None:
            self.conn_string = config.conn_string
        if self.username is None:
            self.username = config.username
        if self.password is None:
            self.password = config.password
        if self.conn_root_certificate:
            self.conn_root_certificate = config.conn_root_certificate
        if self.bucket is None:
            self.bucket = config.bucket
        return self

    def _create_cluster_args(self) -> couchbase.options.ClusterOptions:
        if self.conn_root_certificate is not None and isinstance(self.conn_root_certificate, pathlib.Path):
            conn_root_certificate = self.conn_root_certificate.absolute()
        else:
            conn_root_certificate = self.conn_root_certificate

        return couchbase.options.ClusterOptions(
            couchbase.auth.PasswordAuthenticator(
                username=self.username,
                password=self.password.get_secret_value(),
                cert_path=conn_root_certificate,
            )
        )

    def Cluster(self) -> couchbase.cluster.Cluster:
        return couchbase.cluster.Cluster(self.conn_string, self._create_cluster_args())

    async def AsyncCluster(self) -> acouchbase.cluster.Cluster:
        return await acouchbase.cluster.Cluster.connect(self.conn_string, self._create_cluster_args())
