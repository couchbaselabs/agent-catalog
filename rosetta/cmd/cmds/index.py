import fnmatch
import pathlib

import git

from tqdm import tqdm

from rosetta.cmd.cmds.init import init_local

from rosetta.core.catalog.dir import dir_scan

from rosetta.core.tool.indexer import source_indexers


source_globs = list(source_indexers.keys())


# TODO: During index'ing, should we also record the source_dirs into the catalog?


MAX_ERRS = 10 # TODO: Hardcoded limit on too many errors.


def cmd_index(ctx, source_dirs: list[str], embedding_model: str, **_):
    meta = init_local(ctx, embedding_model)

    if not meta['embedding_model']:
        raise ValueError("An --embedding-model is required as an embedding model is not yet recorded.")

    repo = git.Repo('.')
    if repo.is_dirty():
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

        def rev_ident_fn(filename: pathlib.Path) -> str:
            print("rev_ident_fn", filename)

            # TODO: Call repo GitPython API to retrieve commit SHA,
            # parent SHA, whether the file is dirty, etc.

            return "TODO-rev-ident"

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(p.name, glob):
                errs, descriptors = indexer.start_descriptors(p, rev_ident_fn)

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

    print("==================\nlocal catalog...")

    print("\n".join([str(descriptor) for descriptor, indexer in all_descriptors]))

    # TODO: Actually save the local catalog.

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
