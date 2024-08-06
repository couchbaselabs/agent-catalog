import fnmatch
import os
import pathlib

import git

from tqdm import tqdm

from rosetta.cmd.cmds.init import init_local

from rosetta.core.catalog.dir import dir_scan

from rosetta.core.catalog.descriptor import CatalogDescriptor

from rosetta.core.tool.indexer import source_indexers


source_globs = list(source_indexers.keys())


# TODO: During index'ing, should we also record the source_dirs into the catalog?


MAX_ERRS = 10 # TODO: Hardcoded limit on too many errors.


def commit_str(commit):
    """ Ex: 'g1234abcd'. """

    # TODO: Only works for git, where a far, future day, folks might want non-git?

    return 'g' + str(commit)[:8]


def cmd_index(ctx, source_dirs: list[str], embedding_model: str, **_):
    meta = init_local(ctx, embedding_model)

    if not meta['embedding_model']:
        raise ValueError("An --embedding-model is required as an embedding model is not yet recorded.")

    # The repo is the user's application's repo and is NOT the
    # repo of rosetta-core. The rosetta CLI / library should be run
    # in the current working directory of the user's application's repo.
    #
    # TODO: One day, allow for rosetta CLI / library to run anywhere
    # and the '.' to be optionally passed in as an parameter / option.
    #
    repo = git.Repo('.')

    if repo.is_dirty() and \
        not os.getenv("ROSETTA_REPO_DIRTY_OK", False):
        # The ROSETTA_REPO_DIRTY_OK env var is intended
        # to help during rosetta development.

        # TODO: One day, handle when there are dirty files (either changes
        # not yet committed into git or untracked files w.r.t. git) via
        # a hierarchy of catalogs? A hierarchy of catalogs has advanced
        # cases of file deletions, renames/moves & lineage changes
        # and how those changes can shadow lower-level catalog items.
        #
        # TODO: If the repo is dirty only because .rosetta-catalog/ is
        # dirty, then we might consider going ahead and indexing?
        #
        # TODO: If the repo is dirty because .rosetta-activity/ is
        # dirty, then we might print some helper instructions on
        # adding .rosetta-activity/ to the .gitignore file? Or, should
        # instead preemptively generate a .rosetta-activity/.gitiginore
        # file during init_local()?
        #
        raise ValueError(f"repo is dirty")

    source_files = []
    for d in source_dirs:
        source_files += dir_scan(d, source_globs)

    all_errs = []
    all_descriptors = []

    for source_file in tqdm(source_files):
        if len(all_errs) > MAX_ERRS:
            break

        print(source_file)

        p = pathlib.Path(source_file)

        def get_repo_commit_id(filename: pathlib.Path) -> str:
            commits = list(repo.iter_commits(paths=str(filename), max_count=1))
            if not commits or len(commits) <= 0:
                raise ValueError(f"ERROR: get_repo_commit_id, no commits for filename: {filename}")

            return commit_str(commits[0])

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(p.name, glob):
                errs, descriptors = indexer.start_descriptors(p, get_repo_commit_id)

                all_errs += errs or []
                all_descriptors += [(descriptor, indexer) for descriptor in descriptors]

                break

    if not all_errs:
        print("==================\naugmenting...")

        for descriptor, indexer in tqdm(all_descriptors):
            if len(all_errs) > MAX_ERRS:
                break

            print(descriptor.name)

            errs = indexer.augment_descriptor(descriptor)

            all_errs += errs or []

    if not all_errs:
        print("==================\nvectorizing...")

        import sentence_transformers

        embedding_model_obj = sentence_transformers.SentenceTransformer(meta['embedding_model'])

        for descriptor, indexer in tqdm(all_descriptors):
            if len(all_errs) > MAX_ERRS:
                break

            print(descriptor.name)

            errs = indexer.vectorize_descriptor(descriptor, embedding_model_obj)

            all_errs += errs or []

    if all_errs:
        print("ERROR:", "\n".join([str(e) for e in all_errs]))

        raise all_errs[0]

    print("==================\nsaving local catalog...")

    # TODO: One day, allow users to choose a different branch instead of assuming
    # the HEAD branch, as users currently would have to 'git checkout BRANCH_THEY_WANT'
    # before calling 'rosetta index' -- where if we decide to support an optional
    # branch name parameter, then the Indexer.start_descriptors() methods would
    # need to be provided the file blob streams from git instead of our current
    # approach reading the file contents directly,
    repo_commit_id = commit_str(repo.head.commit)

    c = CatalogDescriptor(
        catalog_schema_version=meta["catalog_schema_version"],
        embedding_model=meta["embedding_model"],
        repo_commit_id=repo_commit_id,
        items=[descriptor for descriptor, indexer in all_descriptors],
    )

    # TODO: We should have a specialized json format here, where currently
    # the vector numbers each take up their own line -- and, instead, we want
    # the array of vector numbers to be all on one line, so that it's more
    # usable for humans and so that 'git diff' outputs are more useful.
    j = c.model_dump_json(round_trip=True, indent=2)

    # TODO: During refactoring, we currently save a "tool-catalog.json" (with a hyphen)
    # instead of "tool_catalog.json" to not break other existing code (publish, find, etc).
    tool_catalog_path = ctx['catalog'] + '/tool-catalog.json'

    # TODO: Support a --dry-run option that doesn't actually update/save any files.

    with pathlib.Path(tool_catalog_path).open('w') as fp:
        fp.write(j)
        fp.write('\n')

    # ---------------------------------

    print("==================\nOLD / pre-refactor indexing...")

    # TODO: Old indexing codepaths that are getting refactored.

    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalIndexer(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta['embedding_model'])
    ).index([pathlib.Path(p) for p in source_dirs])
