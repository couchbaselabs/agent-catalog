import json
import os
import typing

import couchbase.auth

from rosetta.core.catalog import CATALOG_SCHEMA_VERSION
from rosetta.core.catalog.version import lib_version, lib_version_compare, catalog_schema_version_compare


def cmd_init_local(ctx, embedding_models: typing.List[str], **_):
    # Init directories.
    os.makedirs(ctx['catalog'], exist_ok=True)
    os.makedirs(ctx['activity'], exist_ok=True)

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

    lib_v = lib_version(ctx)

    meta = {
        # Version of the local catalog data.
        'catalog_schema_version': CATALOG_SCHEMA_VERSION,

        # Version of the SDK library / tool that last wrote the local catalog data.
        'lib_version': lib_v
    }

    meta_path = ctx['catalog'] + '/meta.json'

    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)

    if catalog_schema_version_compare(meta['catalog_schema_version'], CATALOG_SCHEMA_VERSION) > 0:
        # TODO: Perhaps too strict here and we should instead allow micro versions getting ahead.
        raise ValueError("Version of local catalog's catalog_schema_version is ahead.")

    if lib_version_compare(meta['lib_version'], lib_v) > 0:
        # TODO: Perhaps too strict here and we should instead allow micro versions getting ahead.
        raise ValueError("Version of local catalog's lib_version is ahead.")

    meta['catalog_schema_version'] = CATALOG_SCHEMA_VERSION
    meta['lib_version'] = lib_v

    with open(meta_path, 'w') as f:
        json.dump(meta, f)



def cmd_init_couchbase(embedding_models: typing.List[str],
                       conn_string: str,
                       authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
