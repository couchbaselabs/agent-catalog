import pathlib
import typing

from rosetta.cmd.cmds.init import init_local


# TODO: During index'ing, should we also record the source_dirs into the catalog?
# TODO: Need to handle different kinds, e.g., option --kind="tool" or --kind="prompt", etc.
# TODO: Or, can we avoid having the user / app-developer needing to provide a --kind option
#       and instead just index all the different kinds?

def cmd_index(ctx, source_dirs: typing.List[str], embedding_model: str, **_):
    meta = init_local(ctx, embedding_model)

    if not meta['embedding_model']:
        raise ValueError("An --embedding-model is required as an embedding model is not yet recorded.")

    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalRegistrar(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(meta['embedding_model'])
    ).index([pathlib.Path(p) for p in source_dirs])
