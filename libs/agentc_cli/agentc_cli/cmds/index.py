import click
import datetime
import logging
import os
import pathlib
import re
import typing

from ..cmds.util import load_repository
from ..models.context import Context
from .util import DASHES
from .util import KIND_COLORS
from .util import init_local
from agentc_core.catalog import __version__ as CATALOG_SCHEMA_VERSION
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.catalog.version import lib_version
from agentc_core.defaults import DEFAULT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.defaults import DEFAULT_MAX_ERRS
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


def cmd_index(
    source_dirs: list[str | os.PathLike],
    kinds: list[typing.Literal["tool", "prompt"]],
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    dry_run: bool = False,
    ctx: Context = None,
    **_,
):
    assert all(k in {"tool", "prompt"} for k in kinds)
    if ctx is None:
        ctx = Context()

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
    try:
        version = VersionDescriptor(
            identifier=str(repo.head.commit),
            is_dirty=repo.is_dirty(),
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )
    except ValueError as e:
        if re.findall(r"Reference at '.*' does not exist", str(e)):
            logger.debug(f"No commits found in the repository. Swallowing exception:\n{str(e)}")
            version = VersionDescriptor(
                is_dirty=True,
                timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
            )
        else:
            raise e

    meta_version = MetaVersion(
        schema_version=CATALOG_SCHEMA_VERSION,
        library_version=lib_version(),
    )

    if logger.getEffectiveLevel() == logging.DEBUG:

        def logging_printer(content: str, *args, **kwargs):
            logger.debug(content)
            click.secho(content, *args, **kwargs)

        printer = logging_printer
    else:
        printer = click.secho

    for kind in kinds:
        # TODO: The kind needs a security check as it's part of the path?
        catalog_path = pathlib.Path(ctx.catalog) / (kind + DEFAULT_CATALOG_NAME)
        printer(DASHES, fg=KIND_COLORS[kind])
        printer(kind.upper(), bold=True, fg=KIND_COLORS[kind])
        printer(DASHES, fg=KIND_COLORS[kind])
        next_catalog = index_catalog(
            embedding_model,
            meta_version,
            version,
            get_path_version,
            kind,
            catalog_path,
            source_dirs,
            scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
            printer=printer,
            print_progress=True,
            max_errs=DEFAULT_MAX_ERRS,
        )
        if not dry_run and len(next_catalog.catalog_descriptor.items) > 0:
            next_catalog.dump(catalog_path)
            click.secho("\nCatalog successfully indexed!", fg="green")
        click.secho(DASHES, fg=KIND_COLORS[kind])
