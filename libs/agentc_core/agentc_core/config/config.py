import couchbase.auth
import couchbase.cluster
import couchbase.options
import datetime
import isodate
import logging
import os
import pathlib
import pydantic
import pydantic_settings
import tempfile
import typing
import urllib.parse

from agentc_core.catalog.implementations.base import SearchResult
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_ACTIVITY_ROLLOVER_BYTES
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CLUSTER_DDL_RETRY_ATTEMPTS
from agentc_core.defaults import DEFAULT_CLUSTER_DDL_RETRY_WAIT_SECONDS
from agentc_core.defaults import DEFAULT_CLUSTER_WAIT_UNTIL_READY_SECONDS
from agentc_core.defaults import DEFAULT_DDL_CREATE_INDEX_INTERVAL_SECONDS
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL_NAME
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.defaults import DEFAULT_VERBOSITY_LEVEL
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.provider.provider import ToolProvider

logger = logging.getLogger(__name__)

# Constant to represent the latest snapshot version.
LATEST_SNAPSHOT_VERSION = "__LATEST__"

# To support custom refiners, we must export this model.
SearchResult = SearchResult


class RemoteCatalogConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    conn_string: typing.Optional[str] = None
    """ Couchbase connection string that points to the catalog.

    This Couchbase instance refers to the CB instance used with the :code:`publish` command.
    If there exists no local catalog (e.g., this is deployed in a standalone environment), we will perform all
    :code:`find` commands directly on the remote catalog.
    If this field AND ``$AGENT_CATALOG_PROJECT_PATH`` are specified, we will issue :code:`find` on both the remote
    and local catalog (with local catalog entries taking precedence).

    This field **must** be specified with :py:attr:`username`, :py:attr:`password`, and  :py:attr:`bucket`.
    """

    username: typing.Optional[str] = None
    """ Username associated with the Couchbase instance possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`password`, and :py:attr:`bucket`.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`bucket`.
    """

    conn_root_certificate: typing.Optional[str] = None
    """ Path to the root certificate file for the Couchbase cluster.

    This field is optional and only required if the Couchbase cluster is using a self-signed certificate.
    If specified, this field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`,
    and :py:attr:`password`.
    """

    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`password`.
    """

    log_ttl: typing.Optional[datetime.timedelta] = None
    """ The time to live to attach to all logs forwarded to your Couchbase instance possessing the catalog.

    This field is optional, and a :python:`None` value (the default) indicates that all logs will never expire.
    If specified as a string, durations must be specified as an integer (of seconds) or an ISO 8601 duration.
    """

    max_index_partition: int = 1024
    """ The maximum number of index partitions across all nodes for your cluster.

    This parameter is used by the Search service to build vector indexes on :code:`init`.
    By default, this value is 1024.
    """

    index_partition: typing.Optional[int] = None
    r""" The maximum number of index partitions across all nodes for your cluster.

    This parameter is used by the Search service to build vector indexes on :code:`init`.
    By default, this value is :math:`2 \times \text{number of FTS nodes in your cluster}`.
    More information on index partitioning can be found
    `here <https://docs.couchbase.com/server/current/n1ql/n1ql-language-reference/index-partitioning.html>`_.
    """

    wait_until_ready_seconds: typing.Optional[float] = DEFAULT_CLUSTER_WAIT_UNTIL_READY_SECONDS
    """ Maximum wait time before timing out when connecting to a Couchbase cluster.

    If you have a slow network connection, you may want to increase this value.
    By default, this value is 5 seconds.
    """

    ddl_create_index_interval_seconds: typing.Optional[float] = DEFAULT_DDL_CREATE_INDEX_INTERVAL_SECONDS
    """ Wait time (in seconds) between individual :code:`CREATE INDEX` operations.

    This field is only used by the :code:`init` command during index creation.
    Multiple index creation operations may raise a transient error from the Index Service.
    If you keep running into this issue, raise this value.
    By default, this value is 1 second.
    """

    ddl_retry_attempts: typing.Optional[int] = DEFAULT_CLUSTER_DDL_RETRY_ATTEMPTS
    """ Maximum number of attempts to retry DDL operations.

    This field is only used by the :code:`init` command during scope, collection, and index creation.
    If the number of attempts is exceeded, the command will fail.
    By default, this value is 3 attempts.
    """

    ddl_retry_wait_seconds: typing.Optional[float] = DEFAULT_CLUSTER_DDL_RETRY_WAIT_SECONDS
    """ Wait time (in seconds) between DDL operation retries.

    This field is only used by the :code:`init` command during scope, collection, and index creation.
    By default, this value is 5 seconds.
    """

    @pydantic.field_validator("conn_string")
    @classmethod
    def _conn_string_must_follow_supported_url_pattern(cls, v: str) -> str:
        if v is None:
            # No connection string provided, so we're good.
            return v

        v = v.strip()
        parsed_url = urllib.parse.urlparse(v)
        if parsed_url.scheme not in ["couchbase", "couchbases"] or parsed_url.netloc == "":
            raise ValueError(
                "Malformed $AGENT_CATALOG_CONN_STRING received.\n"
                "Please edit your $AGENT_CATALOG_CONN_STRING and try again.\n"
                "Examples of accepted formats are:\n"
                "\tcouchbase://localhost\n"
                "\tcouchbases://my_capella.cloud.couchbase.com"
            )
        return v

    @pydantic.field_validator("conn_root_certificate")
    @classmethod
    def _certificate_path_must_be_valid_if_not_none(cls, v: str, info: pydantic.ValidationInfo) -> str | None:
        conn_url = info.data["conn_string"]
        if conn_url is not None and "couchbases" in conn_url:
            if v is None:
                raise ValueError(
                    "Could not find the environment variable $AGENT_CATALOG_CONN_ROOT_CERTIFICATE!\n"
                    "Please run 'export AGENT_CATALOG_CONN_ROOT_CERTIFICATE=...' or add "
                    "$AGENT_CATALOG_CONN_ROOT_CERTIFICATE to your .env file and try again."
                )
            elif not os.path.exists(v):
                raise ValueError(
                    "Value provided for variable $AGENT_CATALOG_CONN_ROOT_CERTIFICATE does not exist in your file "
                    "system!\n"
                )
            elif not os.path.isfile(v):
                raise ValueError(
                    "Value provided for variable $AGENT_CATALOG_CONN_ROOT_CERTIFICATE is not a valid path to the "
                    "cluster's root certificate file!\n"
                )
            return v
        return None

    @pydantic.field_validator("log_ttl", mode="before")
    @classmethod
    def _log_ttl_seconds_to_timedelta(cls, v: typing.Any) -> typing.Any:
        if isinstance(v, str):
            try:
                isodate.parse_duration(v)
            except isodate.ISO8601Error as e1:
                try:
                    seconds_from_v = int(v)
                    return datetime.timedelta(seconds=seconds_from_v)
                except ValueError:
                    raise ValueError("Value is not a valid seconds string nor an ISO 8601 string.") from e1
        return v

    @pydantic.field_serializer("password")
    def _serialize_password_as_stars(self, _: pydantic.SecretStr, _info):
        return "***"

    def Cluster(self) -> couchbase.cluster.Cluster:
        if self.conn_string is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_CONN_STRING!\n"
                "Please run 'export AGENT_CATALOG_CONN_STRING=...' or add "
                "$AGENT_CATALOG_CONN_STRING to your .env file and try again."
            )
        if self.username is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_USERNAME!\n"
                "Please run 'export AGENT_CATALOG_USERNAME=...' or add "
                "$AGENT_CATALOG_USERNAME to your .env file and try again."
            )
        if self.password is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_PASSWORD!\n"
                "Please run 'export $AGENT_CATALOG_PASSWORD=...' or add "
                "$AGENT_CATALOG_PASSWORD to your .env file and try again."
            )
        if self.bucket is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_BUCKET!\n"
                "Please run 'export AGENT_CATALOG_BUCKET=...' or add "
                "$AGENT_CATALOG_BUCKET to your .env file and try again."
            )

        auth = (
            couchbase.auth.PasswordAuthenticator(self.username, self.password.get_secret_value())
            if self.conn_root_certificate is None
            else couchbase.auth.PasswordAuthenticator(
                self.username, self.password.get_secret_value(), cert_path=self.conn_root_certificate
            )
        )
        options = couchbase.options.ClusterOptions(auth)
        options.apply_profile("wan_development")

        # Connect to our cluster.
        logger.debug(f"Connecting to Couchbase cluster at {self.conn_string}...")
        cluster = couchbase.cluster.Cluster(self.conn_string, options)
        cluster.wait_until_ready(datetime.timedelta(seconds=self.wait_until_ready_seconds))
        logger.debug("Connection successfully established.")
        return cluster


class ToolRuntimeConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    codegen_output: typing.Optional[pathlib.Path | tempfile.TemporaryDirectory | os.PathLike] = None
    """ Location to save generated Python stubs to, if desired.

    On :py:meth:`find_tools`, tools are dynamically generated and served as annotated Python callables.
    By default, this code is never written to disk.
    If this field is specified, we will write all generated files to the given output directory and serve the generated
    Python callables from these files with a "standard import".
    """

    tool_decorator: typing.Optional[typing.Callable[[ToolProvider.ToolResult], ...]] = None
    """ A Python decorator (function) to apply to each result yielded by :py:meth:`agentc.catalog.Catalog.find_tools`.

    By default, yielded results are callable and possess type annotations + documentation strings, but some agent
    frameworks may ask for tools whose type is tailored to their own framework.
    As an example, in LangChain, vanilla Python functions must be converted to ``langchain_core.tools.BaseTool``
    instances.
    To avoid having to "box" these tools yourself, we accept a callback to perform this boxing on your behalf.
    """

    refiner: typing.Optional[typing.Callable] = lambda results: results
    """ A Python function to post-process results (reranking, pruning, etc...) yielded by the catalog.

    By default, we perform a strict top-K nearest neighbor search for relevant results.
    This function serves to perform any additional reranking and **pruning** before the code generation occurs.
    This function should accept a list of :py:class:`agentc_core.catalog.SearchResult` instances (a model with the
    fields ``entry`` and ``delta``) and return a list of :py:class:`agentc_core.catalog.SearchResult` instances.

    We offer an experimental post-processor to cluster closely related results (using delta as the loss function)
    and subsequently yield the closest cluster (see :py:class:`agentc_core.provider.refiner.ClosestClusterRefiner`).
    """

    secrets: typing.Optional[dict[str, pydantic.SecretStr]] = pydantic.Field(default_factory=dict, frozen=True)
    """
    A map of identifiers to secret values (e.g., Couchbase usernames, passwords, etc...).

    .. card:: Field Description

        Some tools require access to values that cannot be hard-coded into the tool themselves (for security reasons).
        As an example, SQL++ tools require a connection string, username, and password.
        Instead of capturing these raw values in the tool metadata, tool descriptors mandate the specification of a
        map whose values are secret keys.
        These identifiers are read either from the environment or from this ``secrets`` field.

        .. code-block:: yaml

            secrets:
                - couchbase:
                    conn_string: MY_CB_CONN_STRING
                    username: MY_CB_USERNAME
                    password: MY_CB_PASSWORD

        To map the secret keys to values explicitly, users will specify their secrets using this field (secrets).

        .. code-block:: python

            provider = agentc.Catalog(secrets={
                "CB_CONN_STRING": "couchbase//23.52.12.254",
                "CB_USERNAME": "admin_7823",
                "CB_PASSWORD": os.getenv("THE_CB_PASSWORD"),
                "CB_CERTIFICATE": "path/to/cert.pem",
            })
    """


class LocalCatalogConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    project_path: typing.Optional[pathlib.Path] = None
    """ Location of the project root.

    If specified, we expect the ``.agent-catalog`` and ``.agent-activity`` folders to exist under this directory.
    If not specified, the project path is the parent folder of the working Git repository root.
    A typical project structure is as follows::

        MY_PROJECT
        |- .agent-catalog
        |- .agent-activity
        |- .git

    To directly specify the catalog or activity paths, specify values for the ``$AGENT_CATALOG_CATALOG_PATH`` and/or
    ``$AGENT_CATALOG_ACTIVITY_PATH`` fields.
    """

    catalog_path: typing.Optional[pathlib.Path] = None
    """ Location of the catalog folder.

    By default, this value is ``$AGENT_CATALOG_PROJECT_PATH/.agent-catalog``.
    """

    activity_path: typing.Optional[pathlib.Path] = None
    """ Location of the activity folder.

    By default, this value is ``$AGENT_CATALOG_ACTIVITY_PATH/.agent-activity``.
    Set this value explicitly to :python:`None` to avoid logging to disk entirely.
    """

    activity_rollover_bytes: int = DEFAULT_ACTIVITY_ROLLOVER_BYTES
    """ Size of the log file in bytes before rollover + compression occurs.

    By default, this value is 128 :math:`MB` (128_000_000).
    If this value is set to 0, no rollover will occur and logs will not be compressed.
    """

    @pydantic.field_validator("activity_path", mode="before")
    @classmethod
    def _empty_string_is_none_path(cls, v: typing.Any) -> typing.Any:
        if isinstance(v, str) and v == "":
            return None
        else:
            return v

    @pydantic.model_validator(mode="after")
    def _catalog_and_activity_must_align_with_path(self) -> typing.Self:
        # Note: this validator does not care about existence, rather malformed configurations.
        if self.project_path is None or (self.catalog_path is None and self.activity_path is None):
            return self
        if self.catalog_path is not None:  # and self.project_path is not None
            catalog_path_under_project = self.project_path / DEFAULT_CATALOG_FOLDER
            if not self.catalog_path.samefile(catalog_path_under_project):
                raise ValueError(
                    f"AGENT_CATALOG_PROJECT_PATH specified with misaligned AGENT_CATALOG_CATALOG_PATH!\n"
                    f"\t'{catalog_path_under_project}' vs. '{self.catalog_path}'\n"
                    f"Try unsetting either variable (e.g. `unset AGENT_CATALOG_PROJECT_PATH` or "
                    f"`unset AGENT_CATALOG_CATALOG_PATH`."
                )
        if self.activity_path is not None:
            activity_path_under_project = self.project_path / DEFAULT_ACTIVITY_FOLDER
            if not self.catalog_path.samefile(activity_path_under_project):
                raise ValueError(
                    f"AGENT_CATALOG_PROJECT_PATH specified with misaligned AGENT_CATALOG_ACTIVITY_PATH!\n"
                    f"\t'{activity_path_under_project}' vs. '{self.catalog_path}'\n"
                    f"Try unsetting either variable (e.g. `unset AGENT_CATALOG_PROJECT_PATH` or "
                    f"`unset AGENT_CATALOG_ACTIVITY_PATH`."
                )
        return self

    def CatalogPath(self) -> pathlib.Path:
        # If a user has explicitly specified a path, or we have inferred the path previously, serve the path here.
        if self.catalog_path is not None:
            if not self.catalog_path.exists():
                raise ValueError(
                    f"Catalog does not exist at {self.catalog_path.absolute()}!\n"
                    f"If this is a new Agent Catalog instance, please run the 'agentc init' command."
                )
            return self.catalog_path

        # If a catalog path is not set, perform a best-effort search.
        starting_path = self.project_path if self.project_path is not None else pathlib.Path.cwd()
        logger.debug(
            'Starting upwards search for the catalog folder in "%s". Searching for "%s".',
            starting_path,
            DEFAULT_CATALOG_FOLDER,
        )
        if logger.level <= logging.DEBUG:
            items_in_directory = []
            for file in starting_path.iterdir():
                items_in_directory.append(file)
            logger.debug("Items in directory: %s", items_in_directory)

        # Iteratively ascend our starting path until we find the catalog folder.
        working_path = starting_path
        while not (working_path / DEFAULT_CATALOG_FOLDER).exists():
            logger.debug("Searching in %s.", working_path.absolute())
            if working_path.parent == working_path:
                raise ValueError(
                    f"Local catalog not found using an upwards search from {starting_path}!\n"
                    f"If this is a new Agent Catalog instance, please run the 'agentc init' command."
                )
            working_path = working_path.parent
        self.catalog_path = working_path / DEFAULT_CATALOG_FOLDER
        return self.catalog_path

    def ActivityPath(self) -> pathlib.Path:
        # If a user has explicitly specified a path, or we have inferred the path previously, serve the path here.
        if self.activity_path is not None:
            if not self.activity_path.exists():
                raise ValueError(f"Activity (folder) does not exist at {self.catalog_path.absolute()}!")
            return self.activity_path

        # If a catalog path is not set, perform a best-effort search.
        starting_path = self.project_path if self.project_path is not None else pathlib.Path.cwd()
        logger.debug(
            'Starting upwards search for the activity folder. Searching for "%s".',
            DEFAULT_ACTIVITY_FOLDER,
        )

        # Iteratively ascend our starting path until we find the activity folder.
        working_path = starting_path
        while not (working_path / DEFAULT_ACTIVITY_FOLDER).exists():
            if working_path.parent == working_path:
                raise ValueError(f"Activity (folder) not found with search from {starting_path}!")
            working_path = working_path.parent
        self.activity_path = working_path / DEFAULT_ACTIVITY_FOLDER
        return self.activity_path


class EmbeddingModelConfig(LocalCatalogConfig, RemoteCatalogConfig):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL_NAME
    """ The name of the embedding model that Agent Catalog will use when indexing and querying tools and prompts.

    By default, the ``sentence-transformers/all-MiniLM-L12-v2`` model is used.
    """

    embedding_model_url: typing.Optional[str] = None
    """ The base URL of an OpenAI-client-compatible endpoint.

    This field is optional, but if specified we will assume that the model specified by ``embedding_model_name`` is
    accessible by this endpoint.
    """

    embedding_model_auth: typing.Optional[str] = None
    """ The authentication token for the endpoint specified by ``embedding_model_url``.

    For endpoints hosted by OpenAI, this is the API key.
    For endpoints hosted on Capella, this is your JWT.
    """

    sentence_transformers_model_cache: typing.Optional[str] = DEFAULT_MODEL_CACHE_FOLDER
    """ The path to the folder where sentence-transformer embedding models will be cached.

    By default, this is ``$AGENT_CATALOG_PROJECT_PATH/.model-cache``.
    For OpenAI embedding models, this field is ignored.
    """

    sentence_transformers_retry_attempts: typing.Optional[int] = 3
    """ The number of times to retry fetching a sentence-transformers model.

    On the first attempt, we will always try to fetch the model from the cache.
    For all subsequent attempts, we will try to fetch the model from HuggingFace.
    If this field is set to 1, we will error out if the model is not found in the cache.
    By default, this value is 3.
    """

    def EmbeddingModel(self, *load_from: typing.Literal["NAME", "LOCAL", "DB"]) -> EmbeddingModel:
        if len(load_from) == 0:
            load_from = (
                "NAME",
                "LOCAL",
            )
        params = {
            "sentence_transformers_model_cache": self.sentence_transformers_model_cache,
            "sentence_transformers_retry_attempts": self.sentence_transformers_retry_attempts,
        }
        for source in set(load_from):
            match source.upper():
                case "NAME":
                    params["embedding_model_name"] = self.embedding_model_name
                    params["embedding_model_url"] = self.embedding_model_url
                    params["embedding_model_auth"] = self.embedding_model_auth
                case "LOCAL":
                    params["catalog_path"] = self.CatalogPath()
                case "DB":
                    params["cb_bucket"] = self.bucket
                    params["cb_cluster"] = self.Cluster()
                    params["catalog_path"] = self.CatalogPath()
        return EmbeddingModel(**params)


class CommandLineConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    verbosity_level: int = pydantic.Field(default=DEFAULT_VERBOSITY_LEVEL, ge=0, le=2)
    """ Verbosity level of the :command:`agentc` command line tool.

    By default, this value is 0.
    If ``AGENT_CATALOG_DEBUG`` exists, this value is set to 2.
    """

    with_interaction: bool = True
    """ Whether to enable the interaction mode for the :command:`agentc` command line tool.

    By default, this value is True.
    Set this value to False to raise errors when the command line tool requires user input (e.g., when developing
    scripts).
    """


class VersioningConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    catalog_id: str = LATEST_SNAPSHOT_VERSION
    """ The snapshot version to find the tools and prompts for.

    By default, we use the latest snapshot version if the repo is clean.
    This snapshot version is retrieved directly from Git (if the repo is clean).
    If the repo is dirty, we will fetch all tools and prompts from the local catalog (by default).
    If snapshot is specified at search time (i.e., with :py:meth:`find_tools` or :py:meth:`find_prompts`), we
    will use that snapshot version instead.
    """


# We'll take a mix-in approach here.
class Config(
    EmbeddingModelConfig,
    LocalCatalogConfig,
    RemoteCatalogConfig,
    ToolRuntimeConfig,
    CommandLineConfig,
    VersioningConfig,
):
    model_config = pydantic_settings.SettingsConfigDict(env_file=".env", env_prefix="AGENT_CATALOG_", extra="ignore")

    debug: bool = False
    """ Whether or not to display debug messages from all Agent Catalog components.

    By default, this value is False.
    If ``AGENT_CATALOG_VERBOSITY_LEVEL`` is set to 2, this value is set to True.
    """

    @pydantic.model_validator(mode="after")
    def _use_verbosity_level_for_debug(self) -> typing.Self:
        if self.debug:
            self.verbosity_level = 2
        elif self.verbosity_level == 2:
            self.debug = True
        return self

    def model_post_init(self, __context: typing.Any) -> None:
        if self.debug:
            for _logger_name in [
                "agentc",
                "agentc_core",
                "agentc_cli",
                "agentc_langchain",
                "agentc_llamaindex",
                "agentc_testing",
            ]:
                _logger = logging.getLogger(_logger_name)
                _logger.setLevel(logging.DEBUG)
                _logger.addHandler(logging.StreamHandler())
