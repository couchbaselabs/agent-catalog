import fnmatch
import pathlib

import git

from tqdm import tqdm

from rosetta.core.catalog.dir import dir_scan

from rosetta.core.tool.indexer import source_indexers

from rosetta.cmd.cmds.init import init_local


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
        source_files = source_files + dir_scan(d, source_globs)

    all_errs = []
    all_descriptors = []

    for source_file in tqdm(source_files):
        if len(all_errs) > MAX_ERRS:
            break

        import time
        time.sleep(0.1)

        p = pathlib.Path(source_file)

        def rev_ident_fn(filename: pathlib.Path) -> str:
            print("rev_ident_fn", filename)
            return "TODO-rev-ident" # TODO: Call repo GitPython API to retrieve commit SHA.

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(p.name, glob):
                errs, descriptors = None, []

                # TODO: This produces a pydantic error, like...
                #   ERROR: 1 validation error for SemanticSearchMetadata input
                #   Input should be a valid dictionary [type=dict_type,
                #     input_value='{\n  "type": "object",\n...ing" }\n    }\n  }\n}\n', input_type=str]
                #   For further information visit https://errors.pydantic.dev/2.8/v/dict_type
                #
                # errs, descriptors = indexer.start_descriptors(p, rev_ident_fn)

                all_errs += errs or []
                all_descriptors += [(descriptor, indexer) for descriptor in descriptors]

                break

    if not all_errs:
        print("==================\naugmenting...")

        for descriptor, indexer in tqdm(all_descriptors):
            if len(all_errs) > MAX_ERRS:
                break

            all_errs += indexer.augment_descriptor(descriptor) or []

    if not all_errs:
        print("==================\nvectorizing...")

        for descriptor, indexer in tqdm(all_descriptors):
            if len(all_errs) > MAX_ERRS:
                break

            all_errs += indexer.vectorize_descriptor(descriptor) or []

    if all_errs:
        print("ERROR:", "\n".join([str(e) for e in all_errs]))

        raise all_errs[0]

    print("==================\nsaving local catalog...")

    print("\n".join([descriptor for descriptor, indexer in descriptors]))

    # TODO: Actually save the local catalog.

    # ---------------------------------

    # TODO: Old indexing codepaths that are getting refactored.

    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalIndexer(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta['embedding_model'])
    ).index([pathlib.Path(p) for p in source_dirs])
