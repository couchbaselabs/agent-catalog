import os
import typing

import couchbase.auth


def cmd_init_local(ctx, embedding_models: typing.List[str], **_):
    # Init directories.
    os.makedirs(ctx['catalog'], exist_ok=True)
    os.makedirs(ctx['catalog_activity'], exist_ok=True)

    import sentence_transformers

    # Download any embedding models that need to be used at runtime.

    # TODO: We should detect whether downloading will happen (vs if models are
    # already cached) -- and appropriately inform that downloads may take some time.
    for model in embedding_models:
        sentence_transformers.SentenceTransformer(model)

    # TODO: Save the embedding model(s) metadata into the catalog,
    # perhaps in a embedding_models.json file. This is because once
    # we start generating vectors with an embedding model, we should
    # stick with that same embedding model so that all the vectors will
    # be in the same, common, comparable vector space.


def cmd_init_couchbase(embedding_models: typing.List[str],
                       conn_string: str,
                       authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
