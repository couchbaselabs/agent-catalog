import click
import couchbase.cluster
import datetime
import git
import logging
import os
import pathlib
import pydantic
import re
import typing

from ..models.context import Context
from agentc_core.analytics.create import create_analytics_udfs
from agentc_core.catalog import CatalogChain
from agentc_core.catalog import CatalogDB
from agentc_core.catalog import CatalogMem
from agentc_core.catalog import __version__ as CATALOG_SCHEMA_VERSION
from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.catalog.version import lib_version
from agentc_core.defaults import DEFAULT_AUDIT_COLLECTION
from agentc_core.defaults import DEFAULT_AUDIT_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.defaults import DEFAULT_MAX_ERRS
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.util.ddl import create_gsi_indexes
from agentc_core.util.ddl import create_vector_index
from agentc_core.util.models import CouchbaseConnect
from agentc_core.util.models import Keyspace
from agentc_core.util.publish import create_scope_and_collection
from agentc_core.version import VersionDescriptor
from couchbase.cluster import Cluster
from couchbase.exceptions import CouchbaseException

# The following are used for colorizing output.
CATALOG_KINDS = ["prompt", "tool"]
LEVEL_COLORS = {"good": "green", "warn": "yellow", "error": "red"}
KIND_COLORS = {"tool": "bright_magenta", "prompt": "blue", "log": "cyan"}
try:
    DASHES = "-" * os.get_terminal_size().columns
except OSError:
    # We might run into this error while running in a debugger.
    DASHES = "-" * 80

logger = logging.getLogger(__name__)


def load_repository(top_dir: pathlib.Path = None):
    # The repo is the user's application's repo and is NOT the repo
    # of agentc_core. The agentc CLI / library should be run in
    # a directory (or subdirectory) of the user's application's repo,
    # where repo_load() walks up the parent dirs until it finds a .git/ subdirectory.
    if top_dir is None:
        top_dir = pathlib.Path(os.getcwd())
    while not (top_dir / ".git").exists():
        if top_dir.parent == top_dir:
            raise ValueError("Could not find .git directory. Please run agentc within a git repository.")
        top_dir = top_dir.parent

    repo = git.Repo(top_dir / ".git")

    def get_path_version(path: pathlib.Path) -> VersionDescriptor:
        is_dirty, identifier = False, None
        if repo.is_dirty(path=path.absolute()):
            is_dirty = True

        # Even if we are dirty, we want to find a commit id if it exists.
        try:
            commits = list(repo.iter_commits(paths=path.absolute(), max_count=1))
        except ValueError as e:
            if re.findall(r"Reference at '.*' does not exist", str(e)):
                logger.debug(f"No commits found in the repository. Swallowing exception:\n{str(e)}")
                commits = []
            else:
                raise e

        if not commits or len(commits) <= 0:
            is_dirty = True
        else:
            identifier = str(commits[0])

        return VersionDescriptor(
            is_dirty=is_dirty,
            identifier=identifier,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )

    return repo, get_path_version


def get_catalog(
    catalog_path: str,
    bucket: str,
    cluster: couchbase.cluster.Cluster,
    force_db: bool,
    include_dirty: bool,
    kind: typing.Literal["tool", "prompt"],
):
    # We have three options: (1) db catalog, (2) local catalog, or (3) both.
    repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
    catalog_file = pathlib.Path(catalog_path) / (kind + DEFAULT_CATALOG_NAME)
    db_catalog, local_catalog = None, None
    if bucket is not None and cluster is not None:
        # Path #1: Search our DB catalog.
        try:
            embedding_model = EmbeddingModel(
                catalog_path=pathlib.Path(catalog_path),
                cb_bucket=bucket,
                cb_cluster=cluster,
            )
            db_catalog = CatalogDB(cluster=cluster, bucket=bucket, kind=kind, embedding_model=embedding_model)
        except pydantic.ValidationError as e:
            if force_db:
                raise e
    if catalog_file.exists() and not force_db:
        # Path #2: Search our local catalog.
        catalog_path = pathlib.Path(catalog_path) / (kind + DEFAULT_CATALOG_NAME)
        embedding_model = EmbeddingModel(
            catalog_path=pathlib.Path(catalog_path),
        )
        local_catalog = CatalogMem(catalog_path=catalog_file, embedding_model=embedding_model)

        if include_dirty and repo and repo.is_dirty():
            # The repo and any dirty files do not have real commit id's, so use "DIRTY".
            version = VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

            # Scan the same source_dirs that were used in the last "agentc index".
            source_dirs = local_catalog.catalog_descriptor.source_dirs

            # Create a CatalogMem on-the-fly that incorporates the dirty
            # source file items which we'll use instead of the local catalog file.
            meta_version = MetaVersion(schema_version=CATALOG_SCHEMA_VERSION, library_version=lib_version())
            if logger.getEffectiveLevel() == logging.DEBUG:

                def logging_printer(content: str, *args, **kwargs):
                    logger.debug(content)
                    click.secho(content, *args, **kwargs)

                printer = logging_printer
            else:
                printer = click.secho
            local_catalog = index_catalog(
                embedding_model,
                meta_version,
                version,
                get_path_version,
                kind,
                catalog_file,
                source_dirs,
                scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                printer=printer,
                print_progress=True,
                max_errs=DEFAULT_MAX_ERRS,
            )
            click.secho("\n", nl=False)
    # Query the catalog for a list of results.
    if db_catalog and local_catalog:
        # Option #3: Chain the local and db catalogs.
        click.secho("Searching both local and db catalogs.")
        catalog = CatalogChain(local_catalog, db_catalog)
    elif db_catalog:
        click.secho("Searching db catalog.")
        catalog = db_catalog
    elif local_catalog:
        click.secho("Searching local catalog.")
        catalog = local_catalog
    else:
        raise ValueError("No catalog found!")
    return catalog


# TODO: One use case is a user's repo (like agent-catalog-example) might
# have multiple, independent subdirectories in it which should each
# have its own, separate local catalog. We might consider using
# the pattern similar to repo_load()'s searching for a .git/ directory
# and scan up the parent directories to find the first .agent-catalog/
# subdirectory?


def init_local_catalog(ctx: Context):
    # Init directories.
    os.makedirs(ctx.catalog, exist_ok=True)


def init_local_activity(ctx: Context):
    # Init directories.
    os.makedirs(ctx.activity, exist_ok=True)


def init_db_catalog(
    ctx: Context, cluster: Cluster, keyspace_details: Keyspace, connection_details_env: CouchbaseConnect
):
    # Get the bucket manager
    cb = cluster.bucket(keyspace_details.bucket)
    bucket_manager = cb.collections()

    # ---------------------------------------------------------------------------------------- #
    #                               SCOPES and COLLECTIONS                                     #
    # ---------------------------------------------------------------------------------------- #
    for kind in CATALOG_KINDS:
        # Create the metadata collection if it does not exist
        click.secho(f"Now creating scope and collections for the {kind} catalog.", fg="yellow")
        meta_col = kind + DEFAULT_META_COLLECTION_NAME
        (msg, err) = create_scope_and_collection(bucket_manager, scope=keyspace_details.scope, collection=meta_col)
        if err is not None:
            raise ValueError(msg)
        else:
            click.secho(f"Metadata collection for the {kind} catalog has been successfully created!\n", fg="green")

        # Create the catalog collection if it does not exist
        click.secho(f"Now creating the catalog collection for the {kind} catalog.", fg="yellow")
        catalog_col = kind + DEFAULT_CATALOG_COLLECTION_NAME
        (msg, err) = create_scope_and_collection(bucket_manager, scope=keyspace_details.scope, collection=catalog_col)
        if err is not None:
            raise ValueError(msg)
        else:
            click.secho(f"Catalog collection for the {kind} catalog has been successfully created!\n", fg="green")

    # ---------------------------------------------------------------------------------------- #
    #                               GSI and Vector Indexes                                     #
    # ---------------------------------------------------------------------------------------- #
    for kind in CATALOG_KINDS:
        click.secho(f"Now building the GSI indexes for the {kind} catalog.", fg="yellow")
        completion_status, err = create_gsi_indexes(keyspace_details.bucket, cluster, kind, True)
        if not completion_status:
            raise ValueError(f"GSI indexes could not be created \n{err}")
        else:
            click.secho(f"All GSI indexes for the {kind} catalog have been successfully created!\n", fg="green")

        click.secho(f"Now building the vector index for the {kind} catalog.", fg="yellow")
        catalog_path = pathlib.Path(ctx.catalog) / (kind + DEFAULT_CATALOG_NAME)

        try:
            with catalog_path.open("r") as fp:
                catalog_desc = CatalogDescriptor.model_validate_json(fp.read())
        except FileNotFoundError:
            click.secho(
                f"Unable to create vector index for {kind} catalog because dimension of vector can't be determined!\nInitialize the local catalog first, index items and try initializing the db catalog again.\n",
                fg="red",
            )
            continue

        dims = len(catalog_desc.items[0].embedding)
        _, err = create_vector_index(keyspace_details.bucket, kind, connection_details_env, dims)
        if err is not None:
            raise ValueError(f"Vector index could not be created \n{err}")
        else:
            click.secho(f"Vector index for the {kind} catalog has been successfully created!\n", fg="green")


def init_db_auditor(ctx: Context, cluster: Cluster, keyspace_details: Keyspace):
    # Get the bucket manager
    cb = cluster.bucket(keyspace_details.bucket)
    bucket_manager = cb.collections()

    log_col = DEFAULT_AUDIT_COLLECTION
    log_scope = DEFAULT_AUDIT_SCOPE
    click.secho("Now creating scope and collections for the auditor.", fg="yellow")
    (msg, err) = create_scope_and_collection(bucket_manager, scope=log_scope, collection=log_col)
    if err is not None:
        raise ValueError(msg)
    else:
        click.secho("Scope and collection for the auditor have been successfully created!\n", fg="green")

    click.secho("Now creating the analytics UDFs for the auditor.", fg="yellow")
    try:
        create_analytics_udfs(cluster, keyspace_details.bucket)
        click.secho("All analytics UDFs for the auditor have been successfully created!\n", fg="green")
    except CouchbaseException as e:
        click.secho("Analytics views could not be created.", fg="red")
        logger.warning("Analytics views could not be created: %s", e)


def init_local_embedding_model():
    # import only in this function to avoid large import times
    import sentence_transformers

    try:
        sentence_transformers.SentenceTransformer(
            os.getenv("AGENT_CATALOG_EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL),
            tokenizer_kwargs={"clean_up_tokenization_spaces": True},
            cache_folder=DEFAULT_MODEL_CACHE_FOLDER,
            local_files_only=False,
        )
    except Exception as e:
        raise RuntimeError(
            f"Unable to download model {os.getenv("AGENT_CATALOG_EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_MODEL)}!!\n{e}"
        ) from None
