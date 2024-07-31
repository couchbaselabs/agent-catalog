import pathlib
import typing


def cmd_index(ctx, source_dirs: typing.List[str], embedding_model: str, **_):
    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'

    import rosetta.core.tool
    import sentence_transformers

    rosetta.core.tool.LocalRegistrar(
        catalog_file=pathlib.Path(tool_catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(embedding_model)
    ).index([pathlib.Path(p) for p in source_dirs])
