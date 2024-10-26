import click
import couchbase.cluster
import datetime
import git
import logging
import os
import pathlib
import pydantic
import typing

from ..models.context import Context
from agentc_core.catalog import CatalogChain
from agentc_core.catalog import CatalogDB
from agentc_core.catalog import CatalogMem
from agentc_core.catalog import __version__ as CATALOG_SCHEMA_VERSION
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.catalog.version import lib_version
from agentc_core.defaults import DEFAULT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_MAX_ERRS
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.version import VersionDescriptor

# The following are used for colorizing output.
LEVEL_COLORS = {"good": "green", "warn": "yellow", "error": "red"}
KIND_COLORS = {"tool": "bright_magenta", "prompt": "blue"}
try:
    DASHES = "-" * os.get_terminal_size().columns
except OSError:
    # We might run into this error while running in a debugger.
    DASHES = "-" * 80

logger = logging.getLogger(__name__)


def init_local(ctx: Context):
    # Init directories.
    os.makedirs(ctx.catalog, exist_ok=True)
    os.makedirs(ctx.activity, exist_ok=True)

    # (Note: the version checking logic has been moved into index).


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
        commits = list(repo.iter_commits(paths=path.absolute(), max_count=1))
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
