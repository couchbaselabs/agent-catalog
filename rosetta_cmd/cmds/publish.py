import json
import logging
from pathlib import Path

from rosetta_core.catalog.catalog_mem import CatalogMem
from rosetta_util.publish import create_scope_and_collection, CustomPublishEncoder

from ..models import Keyspace, Context

logger = logging.getLogger(__name__)


# TODO (GLENN): I haven't tested these changes, but this signals a move towards a "version" object instead of a string.
# TODO (GLENN): Use click.echo instead of print, and make use of the logger.


def cmd_publish(ctx: Context, kind, annotations: list[dict], cluster, keyspace: Keyspace, printer):
    if kind == "all":
        kind_list = ["tool", "prompt"]
        logger.info("Inserting all catalogs...")
    else:
        kind_list = [kind]

    bucket = keyspace.bucket
    scope = keyspace.scope

    # Get bucket ref
    cb = cluster.bucket(bucket)

    for kind in kind_list:

        catalog_path = Path(ctx.catalog) / (kind + "-catalog.json")
        catalog = CatalogMem.load(catalog_path).catalog_descriptor

        # Get the bucket manager
        bucket_manager = cb.collections()

        # ----------Metadata collection----------
        meta_col = kind + "_metadata"
        (msg, err) = create_scope_and_collection(bucket_manager, scope=scope, collection=meta_col)
        if err is not None:
            printer(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(meta_col)

        # dict to store all the metadata - snapshot related data
        metadata = {el: catalog.model_dump()[el] for el in catalog.model_dump() if el != "items"}

        # add annotations to metadata
        annotations_list = {
            an[0]: an[1].split("+") if "+" in an[1] else an[1] for an in annotations
        }
        metadata.update({"snapshot_annotations": annotations_list})

        printer("Upserting metadata..")
        try:
            key = metadata["version"]["identifier"]
            cb_coll.upsert(key, metadata)
            # printer("Snapshot ",result.key," added to keyspace")
        # TODO (GLENN): Should use the specific exception here instead of 'Exception'.
        except Exception as e:
            logger.error("could not insert: ", e)
            return e
        printer("Metadata added!")

        # ----------Catalog items collection----------
        catalog_col = kind + "_catalog"
        (msg, err) = create_scope_and_collection(
            bucket_manager, scope=scope, collection=catalog_col
        )
        if err is not None:
            printer(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(catalog_col)

        printer("Upserting catalog items..")

        # iterate over individual catalog items
        for item in catalog.items:
            try:
                key = item.identifier

                # serialise object to str
                item = json.dumps(item.model_dump(), cls=CustomPublishEncoder)

                # convert to dict object and insert snapshot id
                item_json: dict = json.loads(item)
                item_json.update({"catalog_identifier": metadata["version"]["identifier"]})
                item_json.update({"snapshot_annotations": annotations_list})

                # upsert docs to CB collection
                cb_coll.upsert(key, item_json)
            except Exception as e:
                logger.error("could not insert: ", e)
                return e

        printer(f"Inserted {kind} catalog successfully!\n")

    logger.info("Successfully inserted all catalogs!")
