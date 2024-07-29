import typing
import pathlib
import os
import couchbase.auth


def cmd_initialize_local(embedding_models: typing.List[str], output_directory: str, history_directory: str, **_):
    import sentence_transformers

    # Download any embedding models that need to be used at runtime.
    for model in embedding_models:
        sentence_transformers.SentenceTransformer(model)

    # Initialize our directories.
    output_directory_path = pathlib.Path(output_directory)
    history_directory_path = pathlib.Path(history_directory)
    if not output_directory_path.exists():
        os.mkdir(output_directory)
    if not history_directory_path.exists():
        os.mkdir(history_directory_path.absolute())


def cmd_initialize_couchbase(sentence_models: typing.List[str], conn_string: str,
                             authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
