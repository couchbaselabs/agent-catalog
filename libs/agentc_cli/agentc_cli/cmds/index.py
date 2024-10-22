import click
import datetime
import logging
import os
import pathlib
import tqdm
import typing

from ..cmds.util import load_repository
from ..models.context import Context
from .util import init_local
from agentc_core.catalog import __version__ as CATALOG_SCHEMA_VERSION
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.catalog.version import lib_version
from agentc_core.defaults import DEFAULT_MAX_ERRS
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.embedding.embedding import EmbeddingModel
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


def cmd_index(
    ctx: Context,
    source_dirs: list[str | os.PathLike],
    kind: typing.Literal["tool", "prompt"],
    embedding_model_name: str,
    dry_run: bool = False,
    **_,
):
    # TODO: If the repo is dirty only because .agent-catalog/ is
    # dirty or because .agent-activity/ is dirty, then we might print
    # some helper instructions for the dev user on commiting the .agent-catalog/
    # and on how to add .agent-activity/ to the .gitignore file? Or, should
    # we instead preemptively generate a .agent-activity/.gitiginore
    # file during init_local()?
    init_local(ctx)

    # TODO: One day, maybe allow users to choose a different branch instead of assuming
    # the HEAD branch, as users currently would have to 'git checkout BRANCH_THEY_WANT'
    # before calling 'agent index' -- where if we decide to support an optional
    # branch name parameter, then the Indexer.start_descriptors() methods would
    # need to be provided the file blob streams from the repo instead of our current
    # approach of opening & reading file contents directly,
    repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
    embedding_model = EmbeddingModel(
        embedding_model_name=embedding_model_name,
        catalog_path=pathlib.Path(ctx.catalog),
    )

    # The version for the repo's HEAD commit.
    version = VersionDescriptor(
        identifier=str(repo.head.commit),
        is_dirty=repo.is_dirty(),
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )

    # TODO: The kind needs a security check as it's part of the path?
    catalog_path = pathlib.Path(ctx.catalog + "/" + kind + "-catalog.json")

    meta_version = MetaVersion(
        schema_version=CATALOG_SCHEMA_VERSION,
        library_version=lib_version(),
    )
    next_catalog = index_catalog(
        embedding_model,
        meta_version,
        version,
        get_path_version,
        kind,
        catalog_path,
        source_dirs,
        scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
        printer=click.echo,
        progress=tqdm.tqdm,
        max_errs=DEFAULT_MAX_ERRS,
    )

    click.echo("==================")
    click.secho("Saving local catalog...", fg="yellow")

    if not dry_run:
        next_catalog.dump(catalog_path)
        click.secho("Successfully saved local catalog.", fg="green")
    else:
        click.secho("Skipping local catalog saving due to --dry-run", fg="yellow")
