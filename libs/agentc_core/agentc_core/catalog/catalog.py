import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import logging
import platform
import pydantic
import typing

from agentc_core.catalog.implementations.base import CatalogBase
from agentc_core.catalog.implementations.base import SearchResult
from agentc_core.catalog.implementations.chain import CatalogChain
from agentc_core.catalog.implementations.db import CatalogDB
from agentc_core.catalog.implementations.mem import CatalogMem
from agentc_core.config import LATEST_SNAPSHOT_VERSION
from agentc_core.config import EmbeddingModelConfig
from agentc_core.config import LocalCatalogConfig
from agentc_core.config import RemoteCatalogConfig
from agentc_core.defaults import DEFAULT_MODEL_INPUT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.provider import ModelInputProvider
from agentc_core.provider import ModelType
from agentc_core.provider import PythonTarget
from agentc_core.provider import ToolProvider
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)

# To support custom refiners, we must export this model.
SearchResult = SearchResult

# To support the generation of different (schema) models, we export this model.
SchemaModel = ModelType

# To support returning prompts with defined tools + the ability to utilize the tool schema, we export this model.
ModelInput = ModelInputProvider.ModelInput
Tool = ToolProvider.ToolResult


class Catalog(RemoteCatalogConfig, LocalCatalogConfig, EmbeddingModelConfig):
    """A provider of indexed "agent building blocks" (e.g., tools, model inputs, etc...)."""

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

    _local_model_input_catalog: CatalogMem = None
    _remote_model_input_catalog: CatalogDB = None
    _model_input_catalog: CatalogBase = None
    _model_input_provider: ModelInputProvider = None

    @pydantic.model_validator(mode="after")
    def _find_local_catalog(self) -> typing.Self:
        try:
            # Note: this method sets the self.catalog_path attribute if found.
            self.CatalogPath()
        except ValueError as e:
            logger.debug(
                f"Local catalog not found when initializing Catalog instance. " f"Swallowing exception {str(e)}."
            )
            return self

        # Note: we will defer embedding model mismatches to the remote catalog validator.
        embedding_model = EmbeddingModel(
            embedding_model_name=self.embedding_model_name,
            embedding_model_auth=self.embedding_model_auth,
            embedding_model_url=self.embedding_model_url,
            sentence_transformers_model_cache=self.sentence_transformers_model_cache,
            catalog_path=self.catalog_path,
        )

        # Set our local catalog if it exists.
        tool_catalog_file = self.catalog_path / DEFAULT_TOOL_CATALOG_FILE
        if tool_catalog_file.exists():
            logger.debug("Loading local tool catalog at %s.", str(tool_catalog_file.absolute()))
            self._local_tool_catalog = CatalogMem(catalog_file=tool_catalog_file, embedding_model=embedding_model)
        model_input_catalog_file = self.catalog_path / DEFAULT_MODEL_INPUT_CATALOG_FILE
        if model_input_catalog_file.exists():
            logger.debug("Loading local model input catalog at %s.", str(model_input_catalog_file.absolute()))
            self._local_model_input_catalog = CatalogMem(
                catalog_file=model_input_catalog_file, embedding_model=embedding_model
            )
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
            cluster: couchbase.cluster.Cluster = self.Cluster()
        except (couchbase.exceptions.CouchbaseException, ValueError) as e:
            logger.warning(
                "Could not connect to the Couchbase cluster. "
                f"Skipping remote catalog and swallowing exception {str(e)}."
            )
            return self

        # Validate the embedding models of our tool and prompt catalogs.
        if self._local_tool_catalog is not None or self._local_model_input_catalog is not None:
            embedding_model = EmbeddingModel(
                cb_bucket=self.bucket,
                cb_cluster=cluster,
                catalog_path=self.CatalogPath(),
                embedding_model_name=self.embedding_model_name,
                embedding_model_auth=self.embedding_model_auth,
                embedding_model_url=self.embedding_model_url,
                sentence_transformers_model_cache=self.sentence_transformers_model_cache,
            )
        else:
            embedding_model = EmbeddingModel(
                cb_bucket=self.bucket,
                cb_cluster=cluster,
                embedding_model_name=self.embedding_model_name,
                embedding_model_auth=self.embedding_model_auth,
                embedding_model_url=self.embedding_model_url,
                sentence_transformers_model_cache=self.sentence_transformers_model_cache,
            )

        try:
            self._remote_tool_catalog = CatalogDB(
                cluster=cluster, bucket=self.bucket, kind="tool", embedding_model=embedding_model
            )
        except pydantic.ValidationError as e:
            logger.debug(
                f"'agentc publish tool' has not been run. "
                f"Skipping remote tool catalog and swallowing exception {str(e)}."
            )
            self._remote_tool_catalog = None
        try:
            self._remote_model_input_catalog = CatalogDB(
                cluster=cluster, bucket=self.bucket, kind="model-input", embedding_model=embedding_model
            )
        except pydantic.ValidationError as e:
            logger.debug(
                "'agentc publish model-input' has not been run. "
                f"Skipping remote model-input catalog and swallowing exception {str(e)}."
            )
            self._remote_model_input_catalog = None
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
            output=self.codegen_output,
            refiner=self.refiner,
            secrets=self.secrets,
            python_version=target_python_version,
            model_type=self.tool_model,
        )
        return self

    # Note: this must be placed **after** _find_local_catalog and _find_remote_catalog.
    @pydantic.model_validator(mode="after")
    def _initialize_model_input_provider(self) -> typing.Self:
        # Set our catalog.
        if self._local_model_input_catalog is None and self._remote_model_input_catalog is None:
            logger.info("No local or remote catalog found. Skipping model-input provider initialization.")
            return self
        if self._local_model_input_catalog is not None and self._remote_model_input_catalog is not None:
            logger.info("A local catalog and a remote catalog have been found. Building a chained model-input catalog.")
            self._model_input_catalog = CatalogChain(self._local_model_input_catalog, self._remote_model_input_catalog)
        elif self._local_model_input_catalog is not None:
            logger.info("Only a local catalog has been found. Using the local model-input catalog.")
            self._model_input_catalog = self._local_model_input_catalog
        else:  # self._remote_model_input_catalog is not None:
            logger.info("Only a remote catalog has been found. Using the remote model-input catalog.")
            self._model_input_catalog = self._remote_model_input_catalog

        # Initialize our model-input provider.
        self._model_input_provider = ModelInputProvider(
            catalog=self._model_input_catalog,
            tool_provider=self._tool_provider,
            refiner=self.refiner,
        )
        return self

    @pydantic.model_validator(mode="after")
    def _one_provider_should_exist(self) -> typing.Self:
        if self._tool_provider is None and self._model_input_provider is None:
            raise ValueError(
                "Could not initialize a tool or model-input provider! "
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
        if self._local_model_input_catalog is not None:
            version_tuples.append(self._local_model_input_catalog.version)
        if self._remote_model_input_catalog is not None:
            version_tuples.append(self._remote_model_input_catalog.version)
        return sorted(version_tuples, key=lambda x: x.timestamp, reverse=True)[0]

    def Scope(self, *args, **kwargs) -> "Scope":
        """A factory method to initialize an Activity instance."""
        # Note: we'll defer the import to avoid circular dependencies.
        from agentc_core.activity import GlobalScope

        return GlobalScope(*args, config=self.config, **kwargs)

    def get(
        self,
        kind: typing.Literal["tool", "model-input"],
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> typing.Union[list[Tool] | ModelInput | None]:
        if kind.lower() == "tool":
            return self.get_tools(query, name, annotations, snapshot, limit)
        elif kind.lower() == "model-input":
            return self.get_inputs(query, name, annotations, snapshot)
        else:
            raise ValueError(f"Unknown item type: {kind}, expected 'tool' or 'model-input'.")

    def get_tools(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[Tool]:
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
                "Please run 'agentc index [SOURCES] --tools' to define a local FS tool catalog."
            )
        if query is not None:
            return self._tool_provider.search(query=query, annotations=annotations, snapshot=snapshot, limit=limit)
        else:
            return [self._tool_provider.get(name=name, annotations=annotations, snapshot=snapshot)]

    def get_inputs(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
    ) -> ModelInput | None:
        """
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param snapshot: The snapshot version to find the tools for. By default, we use the latest snapshot.

        :return: An instance of *ModelInput* class, with the following attributes:
            - **content** (str | dict): The content to be served to the model.
            - **tools** (list): The list containing the tool functions associated with the model input.
            - **output** (str): The output type of the model input, if it exists.
        """
        if self._model_input_provider is None:
            raise RuntimeError(
                "Model-input provider has not been initialized. "
                "Please run 'agentc index [SOURCES] --model-inputs' to define a local FS catalog with model inputs."
            )
        if query is not None:
            results = self._model_input_provider.search(
                query=query, annotations=annotations, snapshot=snapshot, limit=1
            )
            return results[0] if len(results) != 0 else None
        else:
            return self._model_input_provider.get(name=name, annotations=annotations, snapshot=snapshot)
