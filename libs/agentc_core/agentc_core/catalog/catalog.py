import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import logging
import pydantic
import typing

from agentc_core.activity.models.content import Kind as ContentKind
from agentc_core.catalog.implementations.base import CatalogBase
from agentc_core.catalog.implementations.chain import CatalogChain
from agentc_core.catalog.implementations.db import CatalogDB
from agentc_core.catalog.implementations.mem import CatalogMem
from agentc_core.config import LATEST_SNAPSHOT_VERSION
from agentc_core.config import EmbeddingModelConfig
from agentc_core.config import LocalCatalogConfig
from agentc_core.config import RemoteCatalogConfig
from agentc_core.config import ToolRuntimeConfig
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_core.provider import PromptProvider
from agentc_core.provider import ToolProvider
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


# To support returning prompts with defined tools + the ability to utilize the tool schema, we export this model.
Prompt = PromptProvider.PromptResult
Tool = ToolProvider.ToolResult


class Catalog(EmbeddingModelConfig, LocalCatalogConfig, RemoteCatalogConfig, ToolRuntimeConfig):
    """A provider of indexed "agent building blocks" (e.g., tools, prompts, spans...).

    .. card:: Class Description

        A :py:class:`Catalog` instance can be configured in three ways (listed in order of precedence):

        1. Directly (as arguments to the constructor).
        2. Via the environment (though environment variables).
        3. Via a :file:`.env` configuration file.

        In most cases, you'll want to configure your catalog via a :file:`.env` file.
        This style of configuration means you can instantiate a :py:class:`Catalog` instance as such:

        .. code-block:: python

            import agentc
            catalog = agentc.Catalog()

        Some custom configurations can only be specified via the constructor (e.g., ``secrets``).
        For example, if your secrets are managed by some external service (defined below as ``my_secrets_manager``),
        you can specify them as such:

        .. code-block:: python

            import agentc
            catalog = agentc.Catalog(secrets={
                "CB_CONN_STRING": os.getenv("CB_CONN_STRING"),
                "CB_USERNAME": os.getenv("CB_USERNAME"),
                "CB_PASSWORD": my_secrets_manager.get("THE_CB_PASSWORD"),
                "CB_CERTIFICATE": my_secrets_manager.get("PATH_TO_CERT"),
            })

    """

    model_config = pydantic.ConfigDict(extra="ignore")

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
        try:
            # Note: this method sets the self.catalog_path attribute if found.
            self.CatalogPath()
        except ValueError as e:
            logger.debug(
                f"Local catalog not found when initializing Catalog instance. " f"Swallowing exception {str(e)}."
            )
            return self

        # Note: we will defer embedding model mismatches to the remote catalog validator.
        embedding_model = self.EmbeddingModel()

        # Set our local catalog if it exists.
        tool_catalog_file = self.catalog_path / DEFAULT_TOOL_CATALOG_FILE
        if tool_catalog_file.exists():
            logger.debug("Loading local tool catalog at %s.", str(tool_catalog_file.absolute()))
            self._local_tool_catalog = CatalogMem(catalog_file=tool_catalog_file, embedding_model=embedding_model)
        prompt_catalog_file = self.catalog_path / DEFAULT_PROMPT_CATALOG_FILE
        if prompt_catalog_file.exists():
            logger.debug("Loading local prompt catalog at %s.", str(prompt_catalog_file.absolute()))
            self._local_prompt_catalog = CatalogMem(catalog_file=prompt_catalog_file, embedding_model=embedding_model)
        return self

    @pydantic.model_validator(mode="after")
    def _find_remote_catalog(self) -> typing.Self:
        if self.conn_string is None:
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
        if self._local_tool_catalog is not None or self._local_prompt_catalog is not None:
            embedding_model = self.EmbeddingModel("NAME", "LOCAL", "DB")
        else:
            embedding_model = self.EmbeddingModel("NAME", "DB")

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
            self._remote_prompt_catalog = CatalogDB(
                cluster=cluster, bucket=self.bucket, kind="prompt", embedding_model=embedding_model
            )
        except pydantic.ValidationError as e:
            logger.debug(
                "'agentc publish prompt' has not been run. "
                f"Skipping remote prompt catalog and swallowing exception {str(e)}."
            )
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

        # Finally, initialize our provider(s).
        self._tool_provider = ToolProvider(
            catalog=self._tool_catalog,
            decorator=self.tool_decorator,
            output=self.codegen_output,
            refiner=self.refiner,
            secrets=self.secrets,
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
        """The version of the catalog currently being served (i.e., the latest version).

        :returns: An :py:class:`agentc_core.version.VersionDescriptor` instance.
        """

        # We will take the latest version across all catalogs.
        version_tuples = list()
        if self._local_tool_catalog is not None:
            version_tuples += [self._local_tool_catalog.version]
        if self._remote_tool_catalog is not None and len(self._remote_tool_catalog) > 0:
            version_tuples += [self._remote_tool_catalog.version]
        if self._local_prompt_catalog is not None:
            version_tuples += [self._local_prompt_catalog.version]
        if self._remote_prompt_catalog is not None and len(self._remote_prompt_catalog) > 0:
            version_tuples += [self._remote_prompt_catalog.version]
        return sorted(version_tuples, key=lambda x: x.timestamp, reverse=True)[0]

    def Span(
        self,
        name: str,
        session: str = None,
        state: typing.Any = None,
        iterable: bool = False,
        blacklist: set[ContentKind] = None,
        **kwargs,
    ) -> "Span":
        """A factory method to initialize a :py:class:`Span` (more specifically, a :py:class:`GlobalSpan`) instance.

        :param name: Name to bind to each message logged within this span.
        :param session: The run that this tree of spans is associated with. By default, this is a UUID.
        :param state: A JSON-serializable object that will be logged on entering and exiting this span.
        :param iterable: Whether this new span should be iterable. By default, this is :python:`False`.
        :param blacklist: A set of content types to skip logging. By default, there is no blacklist.
        :param kwargs: Additional keyword arguments to pass to the Span constructor.
        """
        from agentc_core.activity import GlobalSpan

        parameters = {
            "config": self,
            "version": self.version,
            "name": name,
            "state": state,
            "iterable": iterable,
            "blacklist": blacklist,
            "kwargs": kwargs,
        }
        if session is not None:
            parameters["session"] = session

        return GlobalSpan(**parameters)

    def find(
        self,
        kind: typing.Literal["tool", "prompt"],
        query: str = None,
        name: str = None,
        annotations: str = None,
        catalog_id: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[Tool] | list[Prompt] | Tool | Prompt | None:
        """Return a list of tools or prompts based on the specified search criteria.

        .. card:: Method Description

            This method is meant to act as the programmatic equivalent of the :code:`agentc find` command.
            Whether (or not) the results are fetched from the local catalog *or* the remote catalog depends on the
            configuration of this :py:class:`agentc_core.catalog.Catalog` instance.

            For example, to find a tool named "get_sentiment_of_text", you would author:

            .. code-block:: python

                results = catalog.find(kind="tool", name="get_sentiment_of_text")
                sentiment_score = results[0].func("I love this product!")

            To find a prompt named "summarize_article_instructions", you would author:

            .. code-block:: python

                results = catalog.find(kind="prompt", name="summarize_article_instructions")
                prompt_for_agent = summarize_article_instructions.content

        :param kind: The type of item to search for, either 'tool' or 'prompt'.
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param catalog_id: The snapshot version to find the tools for. By default, we use the latest snapshot.
        :param limit: The maximum number of results to return (ignored if name is specified).
        :return:
            One of the following:

            * :python:`None` if no results are found by name.
            * "tools" if `kind` is "tool" (see :py:meth:`find_tools` for details).
            * "prompts" if `kind` is "prompt" (see :py:meth:`find_prompts` for details).
        """
        if kind.lower() == "tool":
            return self.find_tools(query, name, annotations, catalog_id, limit)
        elif kind.lower() == "prompt":
            return self.find_prompts(query, name, annotations, catalog_id)
        else:
            raise ValueError(f"Unknown item type: {kind}, expected 'tool' or 'prompt'.")

    def find_tools(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        catalog_id: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[Tool] | Tool | None:
        """Return a list of tools based on the specified search criteria.

        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param catalog_id: The snapshot version to find the tools for. By default, we use the latest snapshot.
        :param limit: The maximum number of results to return (ignored if name is specified).
        :return:
            By default, a list of :py:class:`Tool` instances with the following attributes:

            1. **func** (``typing.Callable``): A Python callable representing the function.
            2. **meta** (:py:type:`RecordDescriptor`): The metadata associated with the tool.
            3. **input** (:py:type:`dict`): The argument schema (in JSON schema) associated with the tool.

            If a ``tool_decorator`` is present, this method will return a list of objects decorated accordingly.
        """
        if self._tool_provider is None:
            raise RuntimeError(
                "Tool provider has not been initialized. "
                "Please run 'agentc index [SOURCES] --tools' to define a local FS tool catalog."
            )
        if query is not None:
            return self._tool_provider.find_with_query(
                query=query, annotations=annotations, snapshot=catalog_id, limit=limit
            )
        else:
            return self._tool_provider.find_with_name(name=name, annotations=annotations, snapshot=catalog_id)

    def find_prompts(
        self,
        query: str = None,
        name: str = None,
        annotations: str = None,
        catalog_id: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[Prompt] | Prompt | None:
        """Return a list of prompts based on the specified search criteria.

        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of ``KEY="VALUE" (AND|OR KEY="VALUE")*``.
        :param catalog_id: The snapshot version to find the tools for. By default, we use the latest snapshot.
        :param limit: The maximum number of results to return (ignored if name is specified).
        :return:
            A list of :py:class:`Prompt` instances, with the following attributes:

            1. **content** (``str`` | ``dict``): The content to be served to the model.
            2. **tools** (``list``): The list containing the tool functions associated with prompt.
            3. **output** (``dict``): The output type of the prompt, if it exists.
            4. **meta** (:py:type:`RecordDescriptor`): The metadata associated with the prompt.
        """
        if self._prompt_provider is None:
            raise RuntimeError(
                "Prompt provider has not been initialized. "
                "Please run 'agentc index [SOURCES] --prompts' to define a local FS catalog with prompts."
            )
        if query is not None:
            return self._prompt_provider.find_with_query(
                query=query, annotations=annotations, snapshot=catalog_id, limit=limit
            )
        else:
            return self._prompt_provider.find_with_name(name=name, annotations=annotations, snapshot=catalog_id)
