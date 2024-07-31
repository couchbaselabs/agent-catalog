import json
import os
import typing

import couchbase.auth

from rosetta.core.catalog import VERSION_CATALOG
from rosetta.core.catalog.version import version, version_compare


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

    v = version(ctx)

    meta = {
        # Version of the local catalog data.
        'version_catalog_schema': VERSION_CATALOG,

        # Version of the tool that last wrote the local catalog data.
        'version_tool': v
    }

    meta_path = ctx['catalog'] + '/meta.json'

    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)

    if version_compare(meta['version_catalog_schema'], v) > 0:
        raise ValueError('Version of local catalog directory is ahead.')

    meta['version_catalog_schema'] = VERSION_CATALOG
    meta['version_tool'] = v

    with open(meta_path, 'w') as f:
        json.dump(meta, f)



def cmd_init_couchbase(embedding_models: typing.List[str],
                       conn_string: str,
                       authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
