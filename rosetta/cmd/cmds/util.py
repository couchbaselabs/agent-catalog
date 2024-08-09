import json
import os
import pathlib

import click
import git
import gitignore_parser
import sentence_transformers

from rosetta.core.catalog import CATALOG_SCHEMA_VERSION
from rosetta.core.catalog.version import (
    catalog_schema_version_compare,
    lib_version,
    lib_version_compare,
)
from rosetta.core.catalog.directory import ScanDirectoryOpts

from ..models.ctx.model import Context


MAX_ERRS = 10


DEFAULT_SCAN_DIRECTORY_OPTS = ScanDirectoryOpts(
    unwanted_patterns = frozenset([".git"]),
    ignore_file_name = ".gitignore",
    ignore_file_parser_factory = gitignore_parser.parse_gitignore)


def init_local(ctx: Context, embedding_model: str, read_only: bool = False):
    # Init directories.
    if not read_only:
        os.makedirs(ctx.catalog, exist_ok=True)
        os.makedirs(ctx.activity, exist_ok=True)
    else:
        print("SKIPPING: local directory creation due to read_only mode")

    lib_v = lib_version()

    meta = {
        # Version of the local catalog data.
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        # Version of the SDK library / tool that last wrote the local catalog data.
        "lib_version": lib_v,
        "embedding_model": None,
    }

    meta_path = ctx.catalog + "/meta.json"

    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)

    if catalog_schema_version_compare(meta["catalog_schema_version"], CATALOG_SCHEMA_VERSION) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's catalog_schema_version is ahead.")

    if lib_version_compare(meta["lib_version"], lib_v) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's lib_version is ahead.")

    meta["catalog_schema_version"] = CATALOG_SCHEMA_VERSION
    meta["lib_version"] = lib_v

    if embedding_model:
        # TODO: There might be other embedding model related options
        # or state that needs recording, like vector size, etc?

        # The embedding model should be the same over the life
        # of the local catalog, so that all the vectors will
        # be in the same, common, comparable vector space.
        meta_embedding_model = meta.get("embedding_model")
        if meta_embedding_model:
            if meta_embedding_model != embedding_model:
                raise ValueError(
                    f"""The embedding model in the local catalog is currently {meta_embedding_model}.
                    Use the 'clean' command to start over with a new embedding model of {embedding_model}."""
                )
        else:
            click.echo(f"Downloading and caching embedding model: {embedding_model} ...")

            # Download embedding model to be cached for later runtime usage.
            sentence_transformers.SentenceTransformer(embedding_model)

            click.echo(f"Downloading and caching embedding model: {embedding_model} ... DONE.")

        meta["embedding_model"] = embedding_model

    if not read_only:
        with open(meta_path, "w") as f:
            json.dump(meta, f, sort_keys=True, indent=4)
    else:
        print("SKIPPING: meta.json file write due to read_only mode")

    return meta


REPO_DIRTY = "_DIRTY_"

def repo_load(top_dir: pathlib.Path = pathlib.Path(os.getcwd())):
    # The repo is the user's application's repo and is NOT the repo
    # of rosetta-core. The rosetta CLI / library should be run in
    # a directory (or subdirectory) of the user's application's repo,
    # where repo_load() walks up the parent dirs until it finds a .git/ subdirectory.

    while not (top_dir / ".git").exists():
        if top_dir.parent == top_dir:
            raise ValueError(
                "Could not find .git directory. Please run index within a git repository."
            )
        top_dir = top_dir.parent

    repo = git.Repo(top_dir / ".git")

    def repo_commit_id_for_path(path: pathlib.Path) -> str:
        path_absolute = path.absolute()

        if repo.is_dirty(path=path_absolute):
            return REPO_DIRTY

        commits = list(repo.iter_commits(paths=path_absolute, max_count=1))
        if not commits or len(commits) <= 0:
            return REPO_DIRTY # Untracked, so treat it as dirty.

        return repo_commit_id_str(commits[0])

    return repo, repo_commit_id_for_path


# TODO: One use case is a user's repo (like rosetta-example) might
# have multiple, independent subdirectories in it which should each
# have its own, separate local catalog. We might consider using
# the pattern similar to repo_load()'s searching for a .git/ directory
# and scan up the parent directories to find the first .rosetta-catalog/
# subdirectory?


def repo_commit_id_str(repo_commit_id):
    """Formats a long repo_commit_id into a shorter format. Ex: 'g1234abcd'."""

    # TODO: Only works for git, where a far, future day, folks might want non-git?

    if repo_commit_id == REPO_DIRTY:
        return REPO_DIRTY

    return "g" + str(repo_commit_id)[:7]

