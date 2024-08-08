import logging
import os
import pathlib

from tqdm import tqdm

from rosetta.cmd.cmds.util import *
from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.core.catalog.directory import scan_directory
from rosetta.core.catalog.descriptor import CatalogDescriptor
from rosetta.core.catalog.index import index_catalog

from ..models.ctx.model import Context


logger = logging.getLogger(__name__)


def cmd_index(ctx: Context, source_dirs: list[str],
              kind: str, embedding_model: str, dry_run: bool, **_):
    meta = init_local(ctx, embedding_model, read_only=dry_run)

    if not meta["embedding_model"]:
        raise ValueError(
            "An --embedding-model is required as an embedding model is not yet recorded."
        )

    repo = repo_load(pathlib.Path(os.getcwd()))

    if repo.is_dirty() and not os.getenv("ROSETTA_REPO_DIRTY_OK", False):
        # The ROSETTA_REPO_DIRTY_OK env var is intended
        # to help during rosetta development.

        # TODO: If the repo is dirty only because .rosetta-catalog/ is
        # dirty or because .rosetta-activity/ is dirty, then we might print
        # some helper instructions for the dev user on commiting the .rosetta-catalog/
        # and on how to add .rosetta-activity/ to the .gitignore file? Or, should
        # we instead preemptively generate a .rosetta-activity/.gitiginore
        # file during init_local()?

        raise ValueError("repo is dirty")

    # TODO: One day, maybe allow users to choose a different branch instead of assuming
    # the HEAD branch, as users currently would have to 'git checkout BRANCH_THEY_WANT'
    # before calling 'rosetta index' -- where if we decide to support an optional
    # branch name parameter, then the Indexer.start_descriptors() methods would
    # need to be provided the file blob streams from the repo instead of our current
    # approach of opening & reading file contents directly,

    # The commit id for the repo's HEAD commit.
    repo_commit_id = commit_str(repo.head.commit)

    # TODO: During refactoring, we currently load/save to "tool-catalog.json" (with
    # a hyphen) instead of the old "tool_catalog.json" to not break other existing
    # code (publish, find, etc) that depends on the old file. Once refactoring is
    # done, we'll switch back to tool_catalog.json.

    # TODO: The kind needs a security check as it's part of the path?
    catalog_path = pathlib.Path(ctx.catalog + "/" + kind + "-catalog.json")

    def get_repo_commit_id(path: pathlib.Path) -> str:
        commits = list(repo.iter_commits(paths=path.absolute(), max_count=1))
        if not commits or len(commits) <= 0:
            raise ValueError(
                f"ERROR: get_repo_commit_id, no commits for filename: {path.absolute()}"
            )
        return commit_str(commits[0])

    next_catalog = index_catalog(meta, repo_commit_id, get_repo_commit_id,
                                 kind, catalog_path, source_dirs,
                                 progress=tqdm, max_errs=MAX_ERRS)

    print("==================\nsaving local catalog...")

    if not dry_run:
        next_catalog.save(catalog_path)
    else:
        print("SKIPPING: local catalog saving due to --dry-run")

    # ---------------------------------

    # TODO: Old indexing codepaths that are getting refactored.

    print("==================\nOLD / pre-refactor indexing...")

    tool_catalog_file = ctx.catalog + "/tool_catalog.json"

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalIndexer(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta["embedding_model"]),
    ).index([pathlib.Path(p) for p in source_dirs])
