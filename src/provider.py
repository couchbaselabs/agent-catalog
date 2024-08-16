import pathlib
import textwrap
import typing
import logging
import pydantic
import pydantic_settings
import rosetta.core.provider
import rosetta.cmd.defaults

from .refiner import SearchResult

logger = logging.getLogger(__name__)


class Provider(pydantic_settings.BaseSettings):
    """ A provider of rosetta indexed "agent building blocks" (e.g., tools). """
    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='ROSETTA_',
        use_attribute_docstrings=True
    )

    conn_string: typing.Annotated[
        pydantic.AnyUrl,
        pydantic.UrlConstraints(
            allowed_schemes=['couchbase', 'couchbases'],
            host_required=True,
            default_host='localhost',
            default_port=8091,
        )
    ]  # TODO (GLENN): Finish this here...
    """ Couchbase connection string that points to the rosetta catalog.
     
    To support 
    """

    # TODO (GLENN): Finish this here...
    username: typing.Optional[pydantic.SecretStr] = None
    password: typing.Optional[pydantic.SecretStr] = None
    bucket: typing.Optional[str] = None

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
    subsequently yield the closest cluster (see rosetta.refiner.ClosestClusterRefiner).
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

    _tool_catalog: rosetta.core.catalog.CatalogBase = None
    _tool_provider: rosetta.core.provider.Provider = None

    @staticmethod
    def _find_local_catalog(starting_path: pathlib.Path) -> pathlib.Path:
        working_path = starting_path

        # Iteratively ascend our starting path until we find the catalog folder.
        while not (working_path / rosetta.cmd.defaults.DEFAULT_CATALOG_FOLDER).exists():
            if working_path.parent == working_path:
                error_message = textwrap.dedent("""
                    Could not find $ROSETTA_CATALOG nor $ROSETTA_CONN_STRING! If this is a new project, please run the
                    command `rosetta index --include-dirty` before instantiating a provider.
                """)
                logger.error(error_message)
                raise ValueError(error_message)
            working_path = working_path.parent

        return working_path

    @pydantic.model_validator(mode='after')
    def _find_and_initialize_catalog_and_provider(self) -> 'Provider':
        if self.catalog is not None:
            # Case #1: the user has explicitly specified $ROSETTA_CATALOG.
            tool_catalog_path = self.catalog / rosetta.cmd.defaults.DEFAULT_TOOL_CATALOG_NAME
            logger.info('Loading local tool catalog at %s.', str(tool_catalog_path.absolute()))
            self._tool_catalog = rosetta.core.catalog.CatalogMem.load(tool_catalog_path)

        elif self.conn_string is not None:
            # Case #2: $ROSETTA_CATALOG is unspecified but $ROSETTA_CONN_STRING is specified.
            use_published_catalog = True
            if self.username is None:
                logger.warning('$ROSETTA_CONN_STRING is specified but $ROSETTA_USERNAME is missing.')
                use_published_catalog = False
            if self.password is None:
                logger.warning('$ROSETTA_CONN_STRING is specified but $ROSETTA_PASSWORD is missing.')
                use_published_catalog = False
            if self.bucket is None:
                logger.warning('$ROSETTA_CONN_STRING is specified but $ROSETTA_BUCKET is missing.')
                use_published_catalog = False

            if not use_published_catalog:
                logger.debug('Starting best effort search for the catalog folder. Searching for "%s".',
                             rosetta.cmd.defaults.DEFAULT_CATALOG_FOLDER)
                tool_catalog_path = Provider._find_local_catalog(pathlib.Path.cwd())
                self._tool_catalog = rosetta.core.catalog.CatalogMem.load(tool_catalog_path)
            else:
                # TODO (GLENN): Load from CatalogDB here.
                raise NotImplementedError('Provider with a remote catalog currently not supported.')

        else:
            # Case #3: Neither $ROSETTA_CATALOG nor $ROSETTA_CONN_STRING is specified.
            logger.debug('Starting best effort search for the catalog folder. Searching for "%s".',
                         rosetta.cmd.defaults.DEFAULT_CATALOG_FOLDER)
            tool_catalog_path = Provider._find_local_catalog(pathlib.Path.cwd())
            self._tool_catalog = rosetta.core.catalog.CatalogMem.load(tool_catalog_path)

        logger.debug('Building provider with the loaded catalog.')
        self._tool_provider = rosetta.core.provider.Provider(
            catalog=self._tool_catalog,
            output=self.output,
            decorator=self.decorator,
            refiner=self.refiner,
            secrets=self.secrets
        )
        return self
