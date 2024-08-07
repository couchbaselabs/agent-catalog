import fnmatch
import logging
import os
import pathlib
import git
from tqdm import tqdm

from rosetta.cmd.cmds.init import init_local
from rosetta.core.catalog.ref import MemCatalogRef
from rosetta.core.catalog.directory import scan_directory
from rosetta.core.catalog.descriptor import CatalogDescriptor
from rosetta.core.tool.indexer import source_indexers, augment_descriptor, vectorize_descriptor


from ..models.ctx.model import Context

source_globs = list(source_indexers.keys())

logger = logging.getLogger(__name__)

# TODO: During index'ing, should we also record the source_dirs into the catalog?


MAX_ERRS = 10  # TODO: Hardcoded limit on too many errors.


def commit_str(commit):
    """Ex: 'g1234abcd'."""

    # TODO: Only works for git, where a far, future day, folks might want non-git?

    return "g" + str(commit)[:7]


def cmd_index(ctx: Context, source_dirs: list[str], embedding_model: str, **_):
    meta = init_local(ctx, embedding_model)

    if not meta["embedding_model"]:
        raise ValueError(
            "An --embedding-model is required as an embedding model is not yet recorded."
        )

    # The repo is the user's application's repo and is NOT the repo
    # of rosetta-core. The rosetta CLI / library should be run in
    # a directory (or subdirectory) of the user's application's repo,
    # where we'll walk up the parent dirs until we find the .git/
    # subdirectory that means we've reached the top directory of the repo.
    working_dir = pathlib.Path(os.getcwd())
    while not (working_dir / ".git").exists():
        if working_dir.parent == working_dir:
            raise ValueError(
                "Could not find .git directory. Please run index within a git repository."
            )
        working_dir = working_dir.parent

    logger.info(f"Found the .git repository in dir: {working_dir}")

    repo = git.Repo(working_dir / ".git")

    if repo.is_dirty() and not os.getenv("ROSETTA_REPO_DIRTY_OK", False):
        # The ROSETTA_REPO_DIRTY_OK env var is intended
        # to help during rosetta development.

        # TODO: One day, handle when there are dirty files (either changes
        # not yet committed into git or untracked files w.r.t. git) via
        # a hierarchy of catalogs? A hierarchy of catalogs has advanced
        # cases of file deletions, renames/moves & lineage changes
        # and how those changes can shadow lower-level catalog items.

        # TODO: If the repo is dirty only because .rosetta-catalog/ is
        # dirty, then we might consider going ahead and indexing?

        # TODO: If the repo is dirty because .rosetta-activity/ is
        # dirty, then we might print some helper instructions on
        # adding .rosetta-activity/ to the .gitignore file? Or, should
        # instead preemptively generate a .rosetta-activity/.gitiginore
        # file during init_local()?

        raise ValueError("repo is dirty")

    # TODO: One day, allow users to choose a different branch instead of assuming
    # the HEAD branch, as users currently would have to 'git checkout BRANCH_THEY_WANT'
    # before calling 'rosetta index' -- where if we decide to support an optional
    # branch name parameter, then the Indexer.start_descriptors() methods would
    # need to be provided the file blob streams from git instead of our current
    # approach of opening & reading file contents directly,

    # The commit id for the repo's HEAD commit.
    repo_commit_id = commit_str(repo.head.commit)

    # TODO: During refactoring, we currently load/save to "tool-catalog.json" (with
    # a hyphen) instead of the old "tool_catalog.json" to not break other existing
    # code (publish, find, etc) that depends on the old file. Once refactoring is
    # done, we'll switch back to tool_catalog.json.

    catalog_path = pathlib.Path(ctx.catalog + "/tool-catalog.json")

    if catalog_path.exists():
        # Load the old / previous local catalog.
        prev_catalog = MemCatalogRef().load(catalog_path)
    else:
        # An empty MemCatalogRef with no items represents an initial catalog state.
        prev_catalog = MemCatalogRef()
        prev_catalog.catalog_descriptor = CatalogDescriptor(
            catalog_schema_version=meta["catalog_schema_version"],
            embedding_model=meta["embedding_model"],
            repo_commit_id="",
            items=[])

    source_files = []
    for source_dir in source_dirs:
        source_files += scan_directory(source_dir, source_globs)

    all_errs = []
    all_descriptors = []
    for source_file in tqdm(source_files):
        if len(all_errs) > MAX_ERRS:
            break

        logger.info(f"Examining source file: {source_file}.")

        def get_repo_commit_id(path: pathlib.Path) -> str:
            commits = list(repo.iter_commits(paths=path.absolute(), max_count=1))
            if not commits or len(commits) <= 0:
                raise ValueError(
                    f"ERROR: get_repo_commit_id, no commits for filename: {path.absolute()}"
                )
            return commit_str(commits[0])

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(source_file.name, glob):
                errs, descriptors = indexer.start_descriptors(source_file, get_repo_commit_id)
                all_errs += errs or []
                all_descriptors += descriptors or []
                break

    if all_errs:
        print("ERROR: during examining", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    print("==================\ndiff'ing...")

    next_catalog = MemCatalogRef()
    next_catalog.catalog_descriptor = CatalogDescriptor(
        catalog_schema_version=meta["catalog_schema_version"],
        embedding_model=meta["embedding_model"],
        repo_commit_id=repo_commit_id,
        items=all_descriptors)

    # TODO: items_newer, items_deleted = prev_catalog.diff(next_catalog)

    if all_errs:
        print("ERROR: during diff'ing", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    print("==================\naugmenting...")

    for descriptor in tqdm(all_descriptors):
        if len(all_errs) > MAX_ERRS:
            break

        print(descriptor.name)

        errs = augment_descriptor(descriptor)

        all_errs += errs or []

    if all_errs:
        print("ERROR: during augmenting", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    print("==================\nvectorizing...")

    import sentence_transformers

    embedding_model_obj = sentence_transformers.SentenceTransformer(meta["embedding_model"])

    for descriptor in tqdm(all_descriptors):
        if len(all_errs) > MAX_ERRS:
            break

        print(descriptor.name)

        errs = vectorize_descriptor(descriptor, embedding_model_obj)

        all_errs += errs or []

    if all_errs:
        print("ERROR: during vectorizing", "\n".join([str(e) for e in all_errs]))

        raise all_errs[0]

    print("==================\nsaving local catalog...")

    # TODO: Support a --dry-run option that doesn't update/save any files.

    next_catalog.save(catalog_path)

    # ---------------------------------

    print("==================\nOLD / pre-refactor indexing...")

    # TODO: Old indexing codepaths that are getting refactored.

    tool_catalog_file = ctx.catalog + "/tool_catalog.json"

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalIndexer(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta["embedding_model"]),
    ).index([pathlib.Path(p) for p in source_dirs])
