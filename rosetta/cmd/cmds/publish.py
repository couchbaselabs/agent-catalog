import json
import os
import logging
from pathlib import Path

from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.utils.publish import (
    create_scope_and_collection,
    CustomPublishEncoder
)

from ..models import (
    Keyspace, Context
)
from ..defaults import (
    DEFAULT_META_CATALOG_NAME
)

logger = logging.getLogger(__name__)


# TODO (GLENN): I haven't tested these changes, but this signals a move towards a "version" object instead of a string.
# TODO (GLENN): Use click.echo instead of print, and make use of the logger.

def cmd_publish_obj(ctx: Context, kind, cluster, keyspace: Keyspace):
    if kind == "all":
        kind_list = ["tool", "prompt"]
        print("Inserting all catalogs...")
    else:
        kind_list = [kind]

    for kind in kind_list:

        catalog_path = Path(ctx.catalog) / (kind + "-catalog.json")
        catalog = CatalogMem.load(catalog_path).catalog_descriptor

        bucket = keyspace.bucket
        scope = keyspace.scope

        # Get bucket ref
        cb = cluster.bucket(bucket)

        # Get the bucket manager
        bucket_manager = cb.collections()

        # ----------Metadata collection----------
        meta_col = kind + "_metadata"
        (msg, err) = create_scope_and_collection(bucket_manager, scope=scope, collection=meta_col)
        if err is not None:
            print(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(meta_col)

        # dict to store all the metadata - snapshot related data
        metadata = {el: catalog.model_dump()[el] for el in catalog.model_dump() if el != 'items'}

        print("Upserting metadata..")
        try:
            key = metadata['version']['identifier']
            cb_coll.upsert(key, metadata)
            # print("Snapshot ",result.key," added to keyspace")
        # TODO (GLENN): Should use the specific exception here instead of 'Exception'.
        except Exception as e:
            print("could not insert: ", e)
            return e
        print("Metadata added!\n")

        # ----------Catalog items collection----------
        catalog_col = kind + "_catalog"
        (msg, err) = create_scope_and_collection(bucket_manager, scope=scope, collection=catalog_col)
        if err is not None:
            print(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(catalog_col)

        print("Upserting catalog items..")

        # iterate over individual catalog items
        for item in catalog.items:
            try:
                key = item.identifier

                # serialise object to str
                item = json.dumps(item.model_dump(), cls=CustomPublishEncoder)

                # convert to dict object and insert snapshot id
                item_json: dict = json.loads(item)
                item_json.update({"catalog_identifier": metadata["version"]["identifier"]})

                # upsert docs to CB collection
                cb_coll.upsert(key, item_json)
            except Exception as e:
                print("could not insert: ", e)
                return e

        print("Inserted", kind, "catalog successfully!\n")

    return "Successfully inserted all catalogs!"
