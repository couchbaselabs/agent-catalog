import pathlib

import git

from rosetta.core.catalog.dir import dir_scan

from rosetta.cmd.cmds.init import init_local


# TODO: This should be defined in rosetta.core somewhere.
source_kinds = {
    '*.py': {},
    '*.sqlpp': {},
    '*.rosetta-yaml': {}
}

# TODO: This should be defined in rosetta.core somewhere.
source_kind_patterns = list(source_kinds.keys())


# TODO: During index'ing, should we also record the source_dirs into the catalog?
# TODO: Need to handle different kinds, e.g., option --kind="tool" or --kind="prompt", etc.
# TODO: Or, can we avoid having the user / app-developer needing to provide a --kind option
#       and instead just index all the different kinds?


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
        source_files = source_files + dir_scan(d, source_kind_patterns)

    for x in source_files:
        print("Candidate:", x)

    # ---------------------------------

    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalRegistrar(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta['embedding_model'])
    ).index([pathlib.Path(p) for p in source_dirs])
