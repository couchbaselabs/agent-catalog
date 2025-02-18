import agentc_core.defaults
import couchbase.auth
import couchbase.cluster
import couchbase.options
import datetime
import logging
import os
import pathlib
import pydantic
import pydantic_settings
import tempfile
import typing
import urllib.parse

logger = logging.getLogger(__name__)

# Constant to represent the latest snapshot version.
LATEST_SNAPSHOT_VERSION = "__LATEST__"


# TODO (GLENN): Add descriptions to each field.


class RemoteCatalogConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    conn_string: typing.Optional[str] = None
    """ Couchbase connection string that points to the catalog.

    This Couchbase instance refers to the CB instance used with the :command:`publish` command.
    If there exists no local catalog (e.g., this is deployed in a standalone environment), we will perform all
    :command:`find` commands directly on the remote catalog.
    If this field AND ``$AGENT_CATALOG_CATALOG`` are specified, we will issue :command:`find` on both the remote and
    local catalog (with local catalog entries taking precedence).

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

    max_index_partition: int = 1024
    """ The maximum number of index partitions across all nodes for your cluster.

    This parameter is used by the Search service to build vector indexes on ``agentc init``.
    By default, this value is 1024.
    """

    index_partition: typing.Optional[int] = None
    """ The maximum number of index partitions across all nodes for your cluster.

    This parameter is used by the Search service to build vector indexes on ``agentc init``.
    By default, this value is ``2 * number of FTS nodes in your cluster``.
    More information on index partitioning can be found `here <https://docs.couchbase.com/server/current/n1ql/n1ql-language-reference/index-partitioning.html>`_.
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
        cluster.wait_until_ready(
            datetime.timedelta(seconds=agentc_core.defaults.DEFAULT_CLUSTER_WAIT_UNTIL_READY_SECONDS)
        )
        logger.debug("Connection successfully established.")
        return cluster


class LocalCatalogConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    project_path: typing.Optional[pathlib.Path] = None
    catalog_path: typing.Optional[pathlib.Path] = None
    activity_path: typing.Optional[pathlib.Path] = None

    codegen_output: typing.Optional[pathlib.Path | tempfile.TemporaryDirectory | os.PathLike] = None
    """ Location to save generated Python stubs to, if desired.

    On :py:meth:`_get_tools_for`, tools are dynamically generated and served as annotated Python callables.
    By default, this code is never written to disk.
    If this field is specified, we will write all generated files to the given output directory and serve the generated
    Python callables from these files with a "standard import".
    """

    embedding_model: str = agentc_core.defaults.DEFAULT_EMBEDDING_MODEL
    """ The name of the embedding model that Agent Catalog will use when indexing and querying tools and model inputs.

    TODO (GLENN): This will be false soon!
    This *must* be a valid embedding model that is supported by the :python:`sentence_transformers.SentenceTransformer`
    class.
    By default, the ``sentence-transformers/all-MiniLM-L12-v2`` model is used.
    """

    @pydantic.model_validator(mode="after")
    def _catalog_and_activity_must_align_with_path(self) -> typing.Self:
        # Note: this validator does not care about existence, rather malformed configurations.
        if self.project_path is None or (self.catalog_path is None and self.activity_path is None):
            return self
        if self.catalog_path is not None:  # and self.project_path is not None
            catalog_path_under_project = self.project_path / agentc_core.defaults.DEFAULT_CATALOG_FOLDER
            if not self.catalog_path.samefile(catalog_path_under_project):
                raise ValueError(
                    f"AGENT_CATALOG_PROJECT_PATH specified with misaligned AGENT_CATALOG_CATALOG_PATH!\n"
                    f"\t'{catalog_path_under_project}' vs. '{self.catalog_path}'\n"
                    f"Try unsetting either variable (e.g. `unset AGENT_CATALOG_PROJECT_PATH` or "
                    f"`unset AGENT_CATALOG_CATALOG_PATH`."
                )
        if self.activity_path is not None:
            activity_path_under_project = self.project_path / agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER
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
            'Starting upwards search for the catalog folder. Searching for "%s".',
            agentc_core.defaults.DEFAULT_CATALOG_FOLDER,
        )

        # Iteratively ascend our starting path until we find the catalog folder.
        working_path = starting_path
        while not (working_path / agentc_core.defaults.DEFAULT_CATALOG_FOLDER).exists():
            if working_path.parent == working_path:
                raise ValueError(
                    f"Local catalog not found using an upwards search from {starting_path}!\n"
                    f"If this is a new Agent Catalog instance, please run the 'agentc init' command."
                )
            working_path = working_path.parent
        self.catalog_path = working_path / agentc_core.defaults.DEFAULT_CATALOG_FOLDER
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
            agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER,
        )

        # Iteratively ascend our starting path until we find the activity folder.
        working_path = starting_path
        while not (working_path / agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER).exists():
            if working_path.parent == working_path:
                raise ValueError(f"Activity (folder) not found with search from {starting_path}!")
            working_path = working_path.parent
        self.activity_path = working_path / agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER
        return self.activity_path


class CommandLineConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    verbosity_level: int = pydantic.Field(agentc_core.defaults.DEFAULT_VERBOSITY_LEVEL, ge=0, le=2)
    with_interaction: bool = True


class VersioningConfig(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    snapshot: str = LATEST_SNAPSHOT_VERSION
    """ The snapshot version to find the tools and prompts for.

    By default, we use the latest snapshot version if the repo is clean.
    This snapshot version is retrieved directly from Git (if the repo is clean).
    If the repo is dirty, we will fetch all tools and prompts from the local catalog (by default).
    If snapshot is specified at search time (i.e., with :py:meth:`_get_tools_for` or :py:meth:`_get_prompt_for`), we
    will use that snapshot version instead.
    """


# We'll take a mix-in approach here.
class Config(LocalCatalogConfig, RemoteCatalogConfig, CommandLineConfig, VersioningConfig):
    model_config = pydantic_settings.SettingsConfigDict(env_prefix="AGENT_CATALOG_")

    debug: bool = False

    def model_post_init(self, __context: typing.Any) -> None:
        if self.debug:
            logging.getLogger("agentc").setLevel(logging.DEBUG)
            logging.getLogger("agentc_core").setLevel(logging.DEBUG)
            logging.getLogger("agentc_cli").setLevel(logging.DEBUG)
            logging.getLogger("agentc_langchain").setLevel(logging.DEBUG)
            logging.getLogger("agentc_testing").setLevel(logging.DEBUG)
