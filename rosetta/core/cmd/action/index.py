import typing
import pathlib


def cmd_index_local(tool_dirs: typing.List[str], catalog_file: str, embedding_model: str, **_):
    import rosetta.core.tools
    import sentence_transformers

    rosetta.core.tools.LocalRegistrar(
        catalog_file=pathlib.Path(catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(embedding_model)
    ).index([pathlib.Path(p) for p in tool_dirs])


def cmd_index_couchbase(tool_dirs: typing.List[str], embedding_model: str, **_):
    # TODO (GLENN): Define an 'index' action for a Couchbase collection.
    pass
