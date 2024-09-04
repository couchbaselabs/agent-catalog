import logging
import pathlib
import pydantic
import pydantic_settings
import rosetta_cmd.defaults
import rosetta_core.provider
import rosetta_core.version
import textwrap
import typing

logger = logging.getLogger(__name__)

# To support custom refiners, we must export this model.
SearchResult = rosetta_core.catalog.SearchResult


class Provider(pydantic_settings.BaseSettings):
    """A provider of Rosetta indexed "agent building blocks" (e.g., tools)."""

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="ROSETTA_", use_attribute_docstrings=True)

    conn_string: typing.Annotated[
        typing.Optional[pydantic.AnyUrl],
        pydantic.UrlConstraints(
            allowed_schemes=["couchbase", "couchbases"],
            host_required=True,
            default_host="localhost",
            default_port=8091,
        ),
    ] = None
    """ Couchbase connection string that points to the Rosetta catalog.

    This Couchbase instance refers to the CB instance used with the publish command. If there exists no local catalog
    (e.g., this is deployed in a standalone environment), we will perform all "find" commands directly on the remote
    catalog. If this field AND $ROSETTA_CATALOG are specified, we will issue "find" on both the remote and local
    catalog.

    This field must be specified with username, password, and bucket.
    """

    username: typing.Optional[pydantic.SecretStr] = None
    """ Username associated with the Couchbase instance possessing the Rosetta catalog.

    This field must be specified with conn_string, password, and bucket.
    """

    password: typing.Optional[pydantic.SecretStr] = None
    """ Password associated with the Couchbase instance possessing the Rosetta catalog.

    This field must be specified with conn_string, username, and bucket.
    """

    bucket: typing.Optional[str] = None
    """ The name of the Couchbase bucket possessing the Rosetta catalog.

    This field must be specified with conn_string, username, and password.
    """

    catalog: typing.Optional[pathlib.Path] = None
    """ Location of the catalog path.

    If this field and $ROSETTA_CONN_STRING are not set, we will perform a best-effort search by walking upward from the
    current working directory until we find the 'rosetta.cmd.defaults.DEFAULT_CATALOG_FOLDER' folder.
    """

    output: typing.Optional[pathlib.Path] = None
    """ Location to save generated Python stubs to, if desired.

    On 'get_tools_for', tools are dynamically generated and served as annotated Python callables. By default, this
    code is never written to disk. If this field is specified, we will write all generated files to the given output
    directory.
    """

    decorator: typing.Optional[typing.Callable[[typing.Callable], typing.Any]] = lambda record: record
    """ A Python decorator (function) to apply to each result yielded by 'get_tools_for'.

    By default, yielded results are callable and possess type annotations + documentation strings, but some agent
    frameworks may ask for tools whose type is tailored to their own framework. As an example, in LangChain, vanilla
    Python functions must be converted to langchain_core.tools.BaseTool instances. To avoid having to "box" these tools
    yourself, we accept a callback to perform this boxing on your behalf.
    """

    refiner: typing.Optional[typing.Callable[[list[SearchResult]], list[SearchResult]]] = lambda results: results
    """ A Python function to post-process results (reranking, pruning, etc...) yielded by the catalog.

    By default, we perform a strict top-K nearest neighbor search for relevant results. This function serves to perform
    any additional reranking and **pruning** before the code generation occurs. This function should accept a list of
    SearchResult instances (a model with the fields "entry" and "delta") and return a list of SearchResult instances.

    We offer an experimental post-processor to cluster closely related results (using delta as the loss function) and
    subsequently yield the closest cluster (see rosetta_core.provider.refiner.ClosestClusterRefiner).
    """

    secrets: typing.Optional[dict[str, pydantic.SecretStr]] = pydantic.Field(default_factory=dict, frozen=True)
    """ A map of identifiers to secret values (e.g., Couchbase usernames, passwords, etc...).

    Some tools require access to values that cannot be hard-coded into the tool themselves (for security reasons). As
    an example, SQL++ tools require a connection string, username, and password. Instead of capturing these raw values
    in the tool metadata, tool descriptors mandate the specification of a map whose values are secret keys.
    ```yaml
    secrets:
        - couchbase:
            conn_string: MY_CB_CONN_STRING
            username: MY_CB_USERNAME
            password: MY_CB_PASSWORD
    ```

    To map the secret keys to values, users will specify their secrets using this field (secrets).
    ```python
    provider = rosetta.Provider(secrets={
        "MY_CB_CONN_STRING": "couchbase//23.52.12.254",
        "MY_CB_USERNAME": "admin_7823",
        "MY_CB_PASSWORD": os.getenv("THE_CB_PASSWORD")
    })
    ```
    """

    _local_tool_catalog: rosetta_core.catalog.CatalogMem = None
    _remote_tool_catalog: rosetta_core.catalog.CatalogDB = None
    _tool_catalog: rosetta_core.catalog.CatalogBase = None
    _tool_provider: rosetta_core.provider.ToolProvider = None

    _local_prompt_catalog: rosetta_core.catalog.CatalogMem = None
    _remote_prompt_catalog: rosetta_core.catalog.CatalogDB = None
    _prompt_catalog: rosetta_core.catalog.CatalogBase = None
    _prompt_provider: rosetta_core.provider.PromptProvider = None

    @pydantic.model_validator(mode="after")
    def _find_local_catalog(self) -> typing.Self:
        if self.catalog is None:
            working_path = pathlib.Path.cwd()
            logger.debug(
                'Starting best effort search for the catalog folder. Searching for "%s".',
                rosetta_cmd.defaults.DEFAULT_CATALOG_FOLDER,
            )

            # Iteratively ascend our starting path until we find the catalog folder.
            while not (working_path / rosetta_cmd.defaults.DEFAULT_CATALOG_FOLDER).exists():
                if working_path.parent == working_path:
                    return self
                working_path = working_path.parent
            self.catalog = working_path / rosetta_cmd.defaults.DEFAULT_CATALOG_FOLDER

        # Set our local catalog if it exists.
        tool_catalog_path = self.catalog / rosetta_cmd.defaults.DEFAULT_TOOL_CATALOG_NAME
        prompt_catalog_path = self.catalog / rosetta_cmd.defaults.DEFAULT_PROMPT_CATALOG_NAME
        logger.info("Loading local tool catalog at %s.", str(tool_catalog_path.absolute()))
        logger.info("Loading local prompt catalog at %s.", str(prompt_catalog_path.absolute()))
        self._local_tool_catalog = rosetta_core.catalog.CatalogMem.load(tool_catalog_path)
        self._local_prompt_catalog = rosetta_core.catalog.CatalogMem.load(prompt_catalog_path)
        return self

    @pydantic.model_validator(mode="after")
    def _find_remote_catalog(self) -> typing.Self:
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

        # TODO (GLENN): Load from CatalogDB here.
        self._remote_tool_catalog = rosetta_core.catalog.CatalogDB()
        return self

    # Note: this must be placed **after** _find_local_catalog and _find_remote_catalog.
    @pydantic.model_validator(mode="after")
    def _initialize_provider(self) -> typing.Self:
        if self._local_tool_catalog is None and self._remote_tool_catalog is None:
            error_message = textwrap.dedent("""
                Could not find $ROSETTA_CATALOG nor $ROSETTA_CONN_STRING! If this is a new project, please run the
                command `rosetta index` before instantiating a provider. Otherwise, please set either of these
                variables.
            """)
            logger.error(error_message)
            raise ValueError(error_message)

        if self._local_tool_catalog is not None and self._remote_tool_catalog is not None:
            logger.debug("Local catalog and remote catalog found. Building a chained catalog.")
            self._tool_catalog = rosetta_core.catalog.CatalogChain(
                chain=[self._local_tool_catalog, self._remote_tool_catalog]
            )
            self._prompt_catalog = rosetta_core.catalog.CatalogChain(
                chain=[self._local_prompt_catalog, self._remote_prompt_catalog]
            )
        else:
            self._tool_catalog = self._local_tool_catalog or self._remote_tool_catalog
            self._prompt_catalog = self._local_prompt_catalog or self._remote_prompt_catalog

        # Finally, initialize our provider.
        self._tool_provider = rosetta_core.provider.ToolProvider(
            catalog=self._tool_catalog,
            output=self.output,
            decorator=self.decorator,
            refiner=self.refiner,
            secrets=self.secrets,
        )
        self._prompt_provider = rosetta_core.provider.PromptProvider(
            catalog=self._prompt_catalog,
            refiner=self.refiner,
        )
        return self

    @pydantic.computed_field
    @property
    def version(self) -> rosetta_core.version.VersionDescriptor:
        return self._tool_catalog.catalog_descriptor.version

    def get_tools_for(
        self, query: str = None, name: str = None, annotations: str = None, limit: typing.Union[int | None] = 1
    ) -> list[typing.Any]:
        """
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of KEY=VALUE (AND|OR KEY=VALUE)*.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        if query is not None:
            return self._tool_provider.search(query=query, annotations=annotations, limit=limit)
        else:
            return self._tool_provider.get(name=name, annotations=annotations, limit=limit)

    def get_prompt_for(self, query: str = None, name: str = None, annotations: str = None) -> str | None:
        """
        :param query: A query string (natural language) to search the catalog with.
        :param name: The specific name of the catalog entry to search for.
        :param annotations: An annotation query string in the form of KEY=VALUE (AND|OR KEY=VALUE)*.
        :return: A single prompt.
        """
        if query is not None:
            results = self._prompt_provider.search(query=query, annotations=annotations, limit=1)
            return results[0] if len(results) != 0 else None
        else:
            return self._prompt_provider.get(name=name, annotations=annotations)
