import click
import couchbase.cluster
import json
import logging
import pathlib
import typing

from ..defaults import DEFAULT_CATALOG_COLLECTION_NAME
from ..defaults import DEFAULT_CATALOG_NAME
from ..defaults import DEFAULT_META_COLLECTION_NAME
from ..models import Context
from rosetta_core.catalog import CatalogMem
from rosetta_util.ddl import create_gsi_indexes
from rosetta_util.ddl import create_vector_index
from rosetta_util.models import CouchbaseConnect
from rosetta_util.models import CustomPublishEncoder
from rosetta_util.models import Keyspace
from rosetta_util.publish import create_scope_and_collection

logger = logging.getLogger(__name__)


def cmd_publish(
    ctx: Context,
    kind: typing.Literal["tool", "prompt", "all"],
    annotations: list[dict],
    cluster: couchbase.cluster.Cluster,
    keyspace: Keyspace,
    printer: typing.Callable[..., None],
    connection_details_env: CouchbaseConnect,
):
    """Command to publish catalog items to user's Couchbase cluster"""

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
        catalog_path = pathlib.Path(ctx.catalog) / (kind + DEFAULT_CATALOG_NAME)
        try:
            catalog = CatalogMem.load(catalog_path)
        except FileNotFoundError:
            # If only one type of catalog is present
            continue
        catalog = catalog.catalog_descriptor
        # embedding_model = catalog.embedding_model.replace("/", "_")

        # Check to ensure a dirty catalog is not published
        if catalog.version.is_dirty:
            click.secho("Cannot publish catalog to DB if dirty!", fg="red")
            click.secho("Please index catalog with a clean repo!", fg="yellow")
            continue

        # Get the bucket manager
        bucket_manager = cb.collections()

        # ---------------------------------------------------------------------------------------- #
        #                                  Metadata collection                                     #
        # ---------------------------------------------------------------------------------------- #
        meta_col = kind + DEFAULT_META_COLLECTION_NAME
        meta_scope = scope
        (msg, err) = create_scope_and_collection(bucket_manager, scope=meta_scope, collection=meta_col)
        if err is not None:
            printer(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(meta_scope).collection(meta_col)

        # dict to store all the metadata - snapshot related data
        metadata = {el: catalog.model_dump()[el] for el in catalog.model_dump() if el != "items"}

        # add annotations to metadata
        annotations_list = {an[0]: an[1].split("+") if "+" in an[1] else an[1] for an in annotations}
        metadata.update({"snapshot_annotations": annotations_list})
        metadata["version"]["timestamp"] = str(metadata["version"]["timestamp"])

        printer("Upserting metadata..")
        try:
            key = metadata["version"]["identifier"]
            cb_coll.upsert(key, metadata)
        # TODO (GLENN): Should use the specific exception here instead of 'Exception'.
        except Exception as e:
            logger.error("could not insert: ", e)
            return e
        printer("Metadata added!")

        # ---------------------------------------------------------------------------------------- #
        #                               Catalog items collection                                   #
        # ---------------------------------------------------------------------------------------- #
        catalog_col = kind + DEFAULT_CATALOG_COLLECTION_NAME
        catalog_scope = scope
        (msg, err) = create_scope_and_collection(bucket_manager, scope=catalog_scope, collection=catalog_col)
        if err is not None:
            printer(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(catalog_scope).collection(catalog_col)

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

                # upsert docs to CB collection
                cb_coll.upsert(key, item_json)
            except Exception as e:
                logger.error("could not insert: ", e)
                return e

        printer(f"Inserted {kind} catalog successfully!\n")

        # ---------------------------------------------------------------------------------------- #
        #                               GSI and Vector Indexes                                     #
        # ---------------------------------------------------------------------------------------- #
        s, err = create_gsi_indexes(bucket, cluster, kind)
        if not s:
            click.secho(f"ERROR: GSI indexes could not be created \n{err}", fg="red")
            return
        else:
            logger.info("Indexes created successfully!")

        dims = len(catalog.items[0].embedding)

        _, err = create_vector_index(bucket, kind, connection_details_env, dims)
        if err is not None:
            click.secho(f"ERROR: Vector index could not be created \n{err}", fg="red")
            return
