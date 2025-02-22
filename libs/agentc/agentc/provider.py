import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import logging
import pathlib
import platform
import pydantic
import pydantic_settings
import tempfile
import typing

from agentc_core.catalog import LATEST_SNAPSHOT_VERSION
from agentc_core.catalog import CatalogBase
from agentc_core.catalog import CatalogChain
from agentc_core.catalog import CatalogDB
from agentc_core.catalog import CatalogMem
from agentc_core.catalog import SearchResult
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.provider import ModelType
from agentc_core.provider import PromptProvider
from agentc_core.provider import PythonTarget
from agentc_core.provider import ToolProvider
from agentc_core.version import VersionDescriptor
from typing import Literal
from typing import Union

logger = logging.getLogger(__name__)

# To support custom refiners, we must export this model.
SearchResult = SearchResult

# To support the generation of different (schema) models, we export this model.
SchemaModel = ModelType

# To support returning prompts with defined tools + the ability to utilize the tool schema, we export this model.
Prompt = PromptProvider.PromptResult
Tool = ToolProvider.ToolResult


class Provider(pydantic_settings.BaseSettings):
    """A provider of indexed "agent building blocks" (e.g., tools)."""

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

    username: typing.Optional[pydantic.SecretStr] = None
    """ Username associated with the Couchbase instance possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`password`, and :py:attr:`bucket`.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`bucket`.
    """

    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket possessing the catalog.

    This field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`, and :py:attr:`password`.
    """

    catalog: typing.Optional[pathlib.Path] = None
    """ Location of the catalog path.

    If this field and ``$AGENT_CATALOG_CONN_STRING`` are not set, we will perform a best-effort search by walking upward
    from the current working directory until we find the :py:data:`agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER` folder.
    """

    conn_root_certificate: typing.Optional[str | pathlib.Path] = None
    """ Path to the root certificate file for the Couchbase cluster.

    This field is optional and only required if the Couchbase cluster is using a self-signed certificate.
    If specified, this field **must** be specified with :py:attr:`conn_string`, :py:attr:`username`,
    and :py:attr:`password`.
    """

    snapshot: typing.Optional[str] = LATEST_SNAPSHOT_VERSION
    """ The snapshot version to find the tools and prompts for.

    By default, we use the latest snapshot version if the repo is clean.
    This snapshot version is retrieved directly from Git (if the repo is clean).
    If the repo is dirty, we will fetch all tools and prompts from the local catalog (by default).
    If snapshot is specified at search time (i.e., with :py:meth:`get_tools_for` or :py:meth:`get_prompt_for`), we will
    use that snapshot version instead.
    """

    provider_output: typing.Optional[pathlib.Path | tempfile.TemporaryDirectory] = None
    """ Location to save generated Python stubs to, if desired.

    On :py:meth:`get_tools_for`, tools are dynamically generated and served as annotated Python callables.
    By default, this code is never written to disk.
    If this field is specified, we will write all generated files to the given output directory and serve the generated
    Python callables from these files with a "standard import".
    """

    decorator: typing.Optional[typing.Callable[[Tool], typing.Any]] = lambda record: record.func
    """ A Python decorator (function) to apply to each result yielded by :py:meth:`get_tools_for`.

    By default, yielded results are callable and possess type annotations + documentation strings, but some agent
    frameworks may ask for tools whose type is tailored to their own framework.
    As an example, in LangChain, vanilla Python functions must be converted to langchain_core.tools.BaseTool instances.
    To avoid having to "box" these tools yourself, we accept a callback to perform this boxing on your behalf.
    """

    refiner: typing.Optional[typing.Callable[[list[SearchResult]], list[SearchResult]]] = lambda results: results
    """ A Python function to post-process results (reranking, pruning, etc...) yielded by the catalog.

    By default, we perform a strict top-K nearest neighbor search for relevant results.
    This function serves to perform any additional reranking and **pruning** before the code generation occurs.
    This function should accept a list of :py:class:`SearchResult` instances (a model with the fields ``entry`` and
    ``delta``) and return a list of :py:class:`SearchResult` instances.

    We offer an experimental post-processor to cluster closely related results (using delta as the loss function) and
    subsequently yield the closest cluster (see :py:class:`agentc_core.provider.refiner.ClosestClusterRefiner`).
    """

    secrets: typing.Optional[dict[str, pydantic.SecretStr]] = pydantic.Field(default_factory=dict, frozen=True)
    """
    A map of identifiers to secret values (e.g., Couchbase usernames, passwords, etc...).

    Some tools require access to values that cannot be hard-coded into the tool themselves (for security reasons).
    As an example, SQL++ tools require a connection string, username, and password.
    Instead of capturing these raw values in the tool metadata, tool descriptors mandate the specification of a
    map whose values are secret keys.

    .. code-block:: yaml

        secrets:
            - couchbase:
                conn_string: MY_CB_CONN_STRING
                username: MY_CB_USERNAME
                password: MY_CB_PASSWORD

    To map the secret keys to values, users will specify their secrets using this field (secrets).

    .. code-block:: python

        provider = agentc.Provider(secrets={
            "MY_CB_CONN_STRING": "couchbase//23.52.12.254",
            "MY_CB_USERNAME": "admin_7823",
            "MY_CB_PASSWORD": os.getenv("THE_CB_PASSWORD")
        })
    """

    tool_model: SchemaModel = SchemaModel.TypingTypedDict
    """ The target model type for the generated (schema) code for tools.

    By default, we generate :py:type:`TypedDict` models and attach these as type hints to the generated Python
    functions.
    Other options include Pydantic (V2 and V1) models and dataclasses, though these may not be supported by all agent
    frameworks.
    """

    _local_tool_catalog: CatalogMem = None
    _remote_tool_catalog: CatalogDB = None
    _tool_catalog: CatalogBase = None
    _tool_provider: ToolProvider = None

    _local_prompt_catalog: CatalogMem = None
    _remote_prompt_catalog: CatalogDB = None
    _prompt_catalog: CatalogBase = None
    _prompt_provider: PromptProvider = None

    @pydantic.model_validator(mode="after")
    def _find_local_catalog(self) -> typing.Self:
        if self.catalog is None:
            working_path = pathlib.Path.cwd()
            logger.debug(
                'Starting best effort search for the catalog folder. Searching for "%s".',
                DEFAULT_CATALOG_FOLDER,
            )

            # Iteratively ascend our starting path until we find the catalog folder.
            while not (working_path / DEFAULT_CATALOG_FOLDER).exists():
                if working_path.parent == working_path:
                    return self
                working_path = working_path.parent
            self.catalog = working_path / DEFAULT_CATALOG_FOLDER

        # Note: we will defer embedding model mismatches to the remote catalog validator.
        embedding_model = EmbeddingModel(catalog_path=self.catalog)

        # Set our local catalog if it exists.
        tool_catalog_path = self.catalog / DEFAULT_TOOL_CATALOG_NAME
        if tool_catalog_path.exists():
            logger.debug("Loading local tool catalog at %s.", str(tool_catalog_path.absolute()))
            self._local_tool_catalog = CatalogMem(catalog_path=tool_catalog_path, embedding_model=embedding_model)
        prompt_catalog_path = self.catalog / DEFAULT_PROMPT_CATALOG_NAME
        if prompt_catalog_path.exists():
            logger.debug("Loading local prompt catalog at %s.", str(prompt_catalog_path.absolute()))
            self._local_prompt_catalog = CatalogMem(catalog_path=prompt_catalog_path, embedding_model=embedding_model)
        return self

    @pydantic.model_validator(mode="after")
    def _find_remote_catalog(self) -> typing.Self:
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

        # Try to connect to our cluster.
        try:
            if self.conn_root_certificate is not None and isinstance(self.conn_root_certificate, pathlib.Path):
                self.conn_root_certificate = self.conn_root_certificate.absolute()
            cluster = couchbase.cluster.Cluster.connect(
                self.conn_string,
                couchbase.options.ClusterOptions(
                    couchbase.auth.PasswordAuthenticator(
                        username=self.username.get_secret_value(),
                        password=self.password.get_secret_value(),
                        cert_path=self.conn_root_certificate,
                    )
                ),
            )
        except couchbase.exceptions.CouchbaseException:
            logger.warning("Could not connect to the Couchbase cluster. Skipping remote catalog.")
            return self

        # Validate the embedding models of our tool and prompt catalogs.
        if self._local_tool_catalog is not None or self._local_prompt_catalog is not None:
            embedding_model = EmbeddingModel(
                cb_bucket=self.bucket,
                cb_cluster=cluster,
                catalog_path=self.catalog,
            )
        else:
            embedding_model = EmbeddingModel(
                cb_bucket=self.bucket,
                cb_cluster=cluster,
            )

        try:
            self._remote_tool_catalog = CatalogDB(
                cluster=cluster, bucket=self.bucket, kind="tool", embedding_model=embedding_model
            )
        except pydantic.ValidationError:
            logger.debug("'agentc publish tool' has not been run. Skipping remote tool catalog.")
            self._remote_tool_catalog = None
        try:
            self._remote_prompt_catalog = CatalogDB(
                cluster=cluster, bucket=self.bucket, kind="prompt", embedding_model=embedding_model
            )
        except pydantic.ValidationError:
            logger.debug("'agentc publish prompt' has not been run. Skipping remote prompt catalog.")
            self._remote_prompt_catalog = None
        return self

    # Note: this must be placed **after** _find_local_catalog and _find_remote_catalog.
    @pydantic.model_validator(mode="after")
    def _initialize_tool_provider(self) -> typing.Self:
        # Set our catalog.
        if self._local_tool_catalog is None and self._remote_tool_catalog is None:
            logger.info("No local or remote catalog found. Skipping tool provider initialization.")
            return self
        if self._local_tool_catalog is not None and self._remote_tool_catalog is not None:
            logger.info("A local catalog and a remote catalog have been found. Building a chained tool catalog.")
            self._tool_catalog = CatalogChain(self._local_tool_catalog, self._remote_tool_catalog)
        elif self._local_tool_catalog is not None:
            logger.info("Only a local catalog has been found. Using the local tool catalog.")
            self._tool_catalog = self._local_tool_catalog
        else:  # self._remote_tool_catalog is not None:
            logger.info("Only a remote catalog has been found. Using the remote tool tool catalog.")
            self._tool_catalog = self._remote_tool_catalog

        # Check the version of Python (this is needed for the code-generator).
        match version_tuple := platform.python_version_tuple():
            case ("3", "6", _):
                target_python_version = PythonTarget.PY_36
            case ("3", "7", _):
                target_python_version = PythonTarget.PY_37
            case ("3", "8", _):
                target_python_version = PythonTarget.PY_38
            case ("3", "9", _):
                target_python_version = PythonTarget.PY_39
            case ("3", "10", _):
                target_python_version = PythonTarget.PY_310
            case ("3", "11", _):
                target_python_version = PythonTarget.PY_311
            case ("3", "12", _):
                target_python_version = PythonTarget.PY_312
            case _:
                if hasattr(version_tuple, "__getitem__") and int(version_tuple[1]) > 12:
                    logger.debug("Python version not recognized. Defaulting to Python 3.11.")
                    target_python_version = PythonTarget.PY_311
                else:
                    raise ValueError(f"Python version {platform.python_version()} not supported.")

        # Finally, initialize our provider(s).
        self._tool_provider = ToolProvider(
            catalog=self._tool_catalog,
            output=self.provider_output,
            decorator=self.decorator,
            refiner=self.refiner,
            secrets=self.secrets,
            python_version=target_python_version,
            model_type=self.tool_model,
        )
        return self

    # Note: this must be placed **after** _find_local_catalog and _find_remote_catalog.
    @pydantic.model_validator(mode="after")
    def _initialize_prompt_provider(self) -> typing.Self:
        # Set our catalog.
        if self._local_prompt_catalog is None and self._remote_prompt_catalog is None:
            logger.info("No local or remote catalog found. Skipping prompt provider initialization.")
            return self
        if self._local_prompt_catalog is not None and self._remote_prompt_catalog is not None:
            logger.info("A local catalog and a remote catalog have been found. Building a chained prompt catalog.")
            self._prompt_catalog = CatalogChain(self._local_prompt_catalog, self._remote_prompt_catalog)
        elif self._local_prompt_catalog is not None:
            logger.info("Only a local catalog has been found. Using the local prompt catalog.")
            self._prompt_catalog = self._local_prompt_catalog
        else:  # self._remote_prompt_catalog is not None:
            logger.info("Only a remote catalog has been found. Using the remote prompt catalog.")
            self._prompt_catalog = self._remote_prompt_catalog

        # Initialize our prompt provider.
        self._prompt_provider = PromptProvider(
            catalog=self._prompt_catalog,
            tool_provider=self._tool_provider,
            refiner=self.refiner,
        )
        return self

    @pydantic.model_validator(mode="after")
    def _one_provider_should_exist(self) -> typing.Self:
        if self._tool_provider is None and self._prompt_provider is None:
            raise ValueError(
                "Could not initialize a tool or prompt provider! "
                "If this is a new project, please run the command `agentc index` before instantiating a provider. "
                "If you are intending to use a remote-only catalog, please ensure that all of the relevant variables "
                "(i.e., conn_string, username, password, and bucket) are set."
            )
        return self

    @pydantic.computed_field
    @property
    def version(self) -> VersionDescriptor:
        # We will take the latest version across all catalogs.
        version_tuples = list()
        if self._local_tool_catalog is not None:
            version_tuples.append(self._local_tool_catalog.version)
        if self._remote_tool_catalog is not None:
            version_tuples.append(self._remote_tool_catalog.version)
        if self._local_prompt_catalog is not None:
            version_tuples.append(self._local_prompt_catalog.version)
        if self._remote_prompt_catalog is not None:
            version_tuples.append(self._remote_prompt_catalog.version)
        return sorted(version_tuples, key=lambda x: x.timestamp, reverse=True)[0]

    def get_item(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
        item_type: Literal["tool", "prompt", "agent"] = None,
    ) -> Union[list[typing.Any] | Prompt | None]:
        if item_type == "tool":
            return self._get_tools_for(query, name, annotations, snapshot, limit)
        elif item_type == "prompt":
            return self._get_prompt_for(query, name, annotations, snapshot)
        elif item_type == "agent":
            pass
        else:
            raise ValueError(f"Unknown item type: {item_type}, expected 'tool', 'prompt', or 'agent'.")

    def _get_tools_for(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[typing.Any]:
        """
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param snapshot: The snapshot version to find the tools for. By default, we use the latest snapshot.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        if self._tool_provider is None:
            raise RuntimeError(
                "Tool provider has not been initialized. "
                "Please run 'agentc index tool' to first build a local tool catalog."
            )
        if query is not None:
            return self._tool_provider.search(query=query, annotations=annotations, snapshot=snapshot, limit=limit)
        else:
            return [self._tool_provider.get(name=name, annotations=annotations, snapshot=snapshot)]

    def _get_prompt_for(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
    ) -> Prompt | None:
        """
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param snapshot: The snapshot version to find the tools for. By default, we use the latest snapshot.

        :return:
                An instance of *PromptResult* class, with the following attributes:
                    - **prompt** (str | jinja2.Template): The prompt content for the agent.
                    - **tools** (list): The list containing the tool functions associated with the prompt.
        """
        if self._prompt_provider is None:
            raise RuntimeError(
                "Prompt provider has not been initialized. "
                "Please run 'agentc index prompt' to first build a local prompt catalog."
            )
        if query is not None:
            results = self._prompt_provider.search(query=query, annotations=annotations, snapshot=snapshot, limit=1)
            return results[0] if len(results) != 0 else None
        else:
            return self._prompt_provider.get(name=name, annotations=annotations, snapshot=snapshot)
