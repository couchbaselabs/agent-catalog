import datetime
import git
import os
import pathlib

from ..models.context import Context
from agentc_core.version import VersionDescriptor


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
        path_absolute = path.absolute()

        if repo.is_dirty(path=path_absolute):
            return VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

        commits = list(repo.iter_commits(paths=path_absolute, max_count=1))
        if not commits or len(commits) <= 0:
            return VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

        return VersionDescriptor(identifier=str(commits[0]), timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

    return repo, get_path_version


# TODO: One use case is a user's repo (like agent-catalog-example) might
# have multiple, independent subdirectories in it which should each
# have its own, separate local catalog. We might consider using
# the pattern similar to repo_load()'s searching for a .git/ directory
# and scan up the parent directories to find the first .agent-catalog/
# subdirectory?
