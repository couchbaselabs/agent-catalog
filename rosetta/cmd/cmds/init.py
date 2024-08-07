import json
import os

import click
import sentence_transformers

from rosetta.core.catalog import CATALOG_SCHEMA_VERSION
from rosetta.core.catalog.version import (
    catalog_schema_version_compare,
    lib_version,
    lib_version_compare,
)

from ..models.ctx.model import Context


def init_local(ctx: Context, embedding_model: str):
    # Init directories.
    os.makedirs(ctx.catalog, exist_ok=True)
    os.makedirs(ctx.activity, exist_ok=True)

    lib_v = lib_version(ctx)

    meta = {
        # Version of the local catalog data.
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        # Version of the SDK library / tool that last wrote the local catalog data.
        "lib_version": lib_v,
        "embedding_model": None,
    }

    meta_path = ctx.catalog + "/meta.json"

    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)

    if catalog_schema_version_compare(meta["catalog_schema_version"], CATALOG_SCHEMA_VERSION) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's catalog_schema_version is ahead.")

    if lib_version_compare(meta["lib_version"], lib_v) > 0:
        # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
        raise ValueError("Version of local catalog's lib_version is ahead.")

    meta["catalog_schema_version"] = CATALOG_SCHEMA_VERSION
    meta["lib_version"] = lib_v

    if embedding_model:
        # TODO: There might be other embedding model related options
        # or state that needs recording, like vector size, etc?

        # The embedding model should be the same over the life
        # of the local catalog, so that all the vectors will
        # be in the same, common, comparable vector space.
        meta_embedding_model = meta.get("embedding_model")
        if meta_embedding_model:
            if meta_embedding_model != embedding_model:
                raise ValueError(
                    f"""The embedding model in the local catalog is currently {meta_embedding_model}.
                    Use the 'clean' command to start over with a new embedding model of {embedding_model}."""
                )
        else:
            click.echo(f"Downloading and caching embedding model: {embedding_model} ...")

            # Download embedding model to be cached for later runtime usage.
            sentence_transformers.SentenceTransformer(embedding_model)

            click.echo(f"Downloading and caching embedding model: {embedding_model} ... DONE.")

        meta["embedding_model"] = embedding_model

    with open(meta_path, "w") as f:
        json.dump(meta, f, sort_keys=True, indent=4)

    return meta
