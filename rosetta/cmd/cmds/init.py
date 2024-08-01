import json
import os

import couchbase.auth

import sentence_transformers

from rosetta.core.catalog import CATALOG_SCHEMA_VERSION
from rosetta.core.catalog.version import lib_version, lib_version_compare, catalog_schema_version_compare


def init_local(ctx, embedding_model: str):
    # Init directories.
    os.makedirs(ctx['catalog'], exist_ok=True)
    os.makedirs(ctx['activity'], exist_ok=True)

    # Download embedding model to be cached for later runtime usage.
    if embedding_model:
        # TODO: We should detect whether downloading will
        # happen (vs if models are already locally cached) and
        # appropriately inform that downloads may take some time,
        # ideally even with a progress bar?
        sentence_transformers.SentenceTransformer(embedding_model)

    lib_v = lib_version(ctx)

    meta = {
        # Version of the local catalog data.
        'catalog_schema_version': CATALOG_SCHEMA_VERSION,

        # Version of the SDK library / tool that last wrote the local catalog data.
        'lib_version': lib_v,

        'embedding_model': embedding_model
    }

    meta_path = ctx['catalog'] + '/meta.json'

    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)

    if catalog_schema_version_compare(meta['catalog_schema_version'], CATALOG_SCHEMA_VERSION) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's catalog_schema_version is ahead.")

    if lib_version_compare(meta['lib_version'], lib_v) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's lib_version is ahead.")

    meta['catalog_schema_version'] = CATALOG_SCHEMA_VERSION
    meta['lib_version'] = lib_v

    if embedding_model:
        # TODO: There might be other embedding model related
        # choices or state, like vector size, etc?

        # The embedding model should be the same over the life
        # of the local catalog, so that all the vectors will
        # be in the same, common, comparable vector space.
        meta_embedding_model = meta.get('embedding_model')
        if meta_embedding_model and \
           meta_embedding_model != embedding_model:
            raise ValueError(f"""The embedding model in the local catalog is currently {meta_embedding_model}.
                             Use the 'clean' command to start over with a new embedding model of {embedding_model}.""")

        meta['embedding_model'] = embedding_model

    with open(meta_path, 'w') as f:
        json.dump(meta, f, sort_keys=True, indent=4)

    return meta


def init_db(embedding_model: str,
            conn_string: str,
            authenticator: couchbase.auth.Authenticator, **_):
    # TODO (GLENN): Add initialization steps to create CB collections here.
    pass
