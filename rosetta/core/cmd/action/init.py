import os
import pathlib
import typing

import couchbase.auth


def cmd_init_local(ctx, embedding_models: typing.List[str], history_dir: str, **_):
    import sentence_transformers

    # Download any embedding models that need to be used at runtime.
    # TODO: We should detect whether downloading will happen (vs if models are
    # already cached) -- and appropriately inform that this may take some time.
    for model in embedding_models:
        sentence_transformers.SentenceTransformer(model)

    # Init directories.
    catalog_dir_path = pathlib.Path(ctx['catalog'])
    if not catalog_dir_path.exists():
        os.mkdir(catalog_dir_path)

    history_dir_path = pathlib.Path(history_dir)
    if not history_dir_path.exists():
        os.mkdir(history_dir_path.absolute())


def cmd_init_couchbase(embedding_models: typing.List[str],
                       conn_string: str,
                       authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
