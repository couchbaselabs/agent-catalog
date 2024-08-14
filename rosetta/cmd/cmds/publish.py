import json
import os
from pathlib import Path

from ..models.publish.model import Keyspace
from ...utils.publish import create_scope_and_collection, CustomPublishEncoder
from ..models.ctx.model import Context
from ...core.catalog.catalog_mem import CatalogMem


def cmd_publish(ctx: Context, cluster, keyspace: Keyspace):
    bucket = keyspace.bucket
    scope = keyspace.scope
    catalog_file_name = ctx.catalog

    folder_path = Path("./" + catalog_file_name)
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

    # Get bucket ref
    cb = cluster.bucket(bucket)

    # Get the bucket manager
    bucket_manager = cb.collections()

    # Iterate over all catalog files
    for col_type in files:
        if str(col_type) == "meta.json":
            continue

        # Get catalog file
        f = open("./" + catalog_file_name + "/" + col_type)
        data = json.load(f)

        # ----------Metadata collection----------
        meta_col = col_type.split("-")[0] + "_metadata"
        (msg, err) = create_scope_and_collection(bucket_manager, scope=scope, collection=meta_col)
        if err is not None:
            print(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(meta_col)

        # dict to store all the metadata - snapshot related data
        metadata = {}
        for key in data:
            if not isinstance(data[key], list):
                # print(f"{key}: {data[key]}")
                metadata.update({key: data[key]})

        print("Upserting metadata..")
        try:
            key = metadata["snapshot_commit_id"]
            cb_coll.upsert(key, metadata)
            # print("Snapshot ",result.key," added to keyspace")
        except Exception as e:
            print("could not insert: ", e)
            return e

        # ----------Catalog items collection----------
        catalog_col = col_type.split("-")[0] + "_catalog"
        (msg, err) = create_scope_and_collection(
            bucket_manager, scope=scope, collection=catalog_col
        )
        if err is not None:
            print(msg, err)
            return

        # get collection ref
        cb_coll = cb.scope(scope).collection(catalog_col)

        print("Upserting catalog items..")

        for item in data["items"]:
            try:
                key = item["identifier"]
                item.update({"snapshot_commit_id": metadata["snapshot_commit_id"]})
                cb_coll.upsert(key, item)
                # print("Snapshot ",result.key," added to keyspace")
            except Exception as e:
                print("could not insert: ", e)
                return e

        f.close()
        print("Inserted", col_type.split("-")[0], "catalog successfully!\n")

    return "Successfully inserted all catalogs!"


def cmd_publish_obj(ctx: Context, kind, cluster, keyspace: Keyspace):
    if kind == "all":  # TODO: handle case later
        print("all catalogs")
        return

    catalog_path = Path(ctx.catalog) / (kind + "-catalog.json")
    catalog = CatalogMem.load(catalog_path).catalog_descriptor

    bucket = keyspace.bucket
    scope = keyspace.scope
    # catalog_file_name = ctx.catalog

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
    metadata = {}
    for element in catalog:
        # print(element[0], type(element[1]))
        if element[0] != "items":
            # print(element[0], element[1])
            metadata.update({element[0]: str(element[1])})

    print("Upserting metadata..")
    try:
        key = metadata["snapshot_commit_id"]
        cb_coll.upsert(key, metadata)
        # print("Snapshot ",result.key," added to keyspace")
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
            item_json.update({"snapshot_commit_id": metadata["snapshot_commit_id"]})

            # upsert docs to CB collection
            cb_coll.upsert(key, item_json)
        except Exception as e:
            print("could not insert: ", e)
            return e

    print("Inserted", kind, "catalog successfully!\n")

    return "Successfully inserted all catalogs!"
