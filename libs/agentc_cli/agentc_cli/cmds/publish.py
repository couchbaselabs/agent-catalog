import click
import json
import logging
import pathlib
import tqdm
import typing

from ..models import Context
from .util import DASHES
from .util import KIND_COLORS
from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.defaults import DEFAULT_CATALOG_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.util.ddl import create_gsi_indexes
from agentc_core.util.ddl import create_vector_index
from agentc_core.util.models import CouchbaseConnect
from agentc_core.util.models import CustomPublishEncoder
from agentc_core.util.models import Keyspace
from agentc_core.util.publish import create_scope_and_collection
from agentc_core.util.publish import get_connection
from couchbase.exceptions import CouchbaseException

logger = logging.getLogger(__name__)


def cmd_publish(
    kind: list[typing.Literal["tool", "prompt"]],
    bucket: str = None,
    keyspace: Keyspace = None,
    annotations: list[dict] = None,
    connection_details_env: CouchbaseConnect = None,
    connection_string: str = None,
    username: str = None,
    password: str = None,
    hostname: str = None,
    ctx: Context = None,
):
    """Command to publish catalog items to user's Couchbase cluster"""
    if ctx is None:
        ctx = Context()

    if connection_details_env is None and None not in [connection_string, username, password, hostname]:
        # Note: validation of the connection details occur here.
        connection_details_env = CouchbaseConnect(
            connection_url=connection_string, username=username, password=password, host=hostname
        )
    elif connection_details_env is None and None in [connection_string, username, password, hostname]:
        raise ValueError("Connection details not provided!")

    if keyspace is not None:
        bucket = keyspace.bucket
        scope = keyspace.scope
    elif bucket is None:
        bucket = bucket
        scope = DEFAULT_CATALOG_SCOPE
    else:
        raise ValueError("Keyspace or bucket name not provided!")

    if annotations is None:
        annotations = list()

    # Get bucket ref
    err, cluster = get_connection(conn=connection_details_env)
    if err:
        raise ValueError(f"Unable to connect to Couchbase!\n{err}")
    cb = cluster.bucket(bucket)

    for k in kind:
        click.secho(DASHES, fg=KIND_COLORS[k])
        click.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
        click.secho(DASHES, fg=KIND_COLORS[k])
        catalog_path = pathlib.Path(ctx.catalog) / (k + DEFAULT_CATALOG_NAME)
        try:
            with catalog_path.open("r") as fp:
                catalog_desc = CatalogDescriptor.model_validate_json(fp.read())
        except FileNotFoundError:
            # If only one type of catalog is present
            continue

        # Check to ensure a dirty catalog is not published
        if catalog_desc.version.is_dirty:
            raise ValueError(
                "Cannot publish a dirty catalog to the DB!\n"
                "Please index your catalog with a clean repo by using 'git commit' and then 'agentc index'.\n"
                "'git status' should show no changes before you run 'agentc index'."
            )

        # Get the bucket manager
        bucket_manager = cb.collections()

        # ---------------------------------------------------------------------------------------- #
        #                                  Metadata collection                                     #
        # ---------------------------------------------------------------------------------------- #
        meta_col = k + DEFAULT_META_COLLECTION_NAME
        meta_scope = scope
        (msg, err) = create_scope_and_collection(bucket_manager, scope=meta_scope, collection=meta_col)
        if err is not None:
            raise ValueError(msg)

        # get collection ref
        cb_coll = cb.scope(meta_scope).collection(meta_col)

        # dict to store all the metadata - snapshot related data
        metadata = {el: catalog_desc.model_dump()[el] for el in catalog_desc.model_dump() if el != "items"}

        # add annotations to metadata
        annotations_list = {an[0]: an[1].split("+") if "+" in an[1] else an[1] for an in annotations}
        metadata.update({"snapshot_annotations": annotations_list})
        metadata["version"]["timestamp"] = str(metadata["version"]["timestamp"])

        logger.debug(f"Now processing the metadata for the {k} catalog.")
        try:
            key = metadata["version"]["identifier"]
            cb_coll.upsert(key, metadata)
        except CouchbaseException as e:
            raise ValueError(f"Couldn't insert metadata!\n{e.message}") from e
        click.secho("Using the catalog identifier: ", nl=False)
        click.secho(metadata["version"]["identifier"] + "\n", bold=True, fg=KIND_COLORS[k])

        # ---------------------------------------------------------------------------------------- #
        #                               Catalog items collection                                   #
        # ---------------------------------------------------------------------------------------- #
        catalog_col = k + DEFAULT_CATALOG_COLLECTION_NAME
        catalog_scope = scope
        (msg, err) = create_scope_and_collection(bucket_manager, scope=catalog_scope, collection=catalog_col)
        if err is not None:
            raise ValueError(msg)

        # get collection ref
        cb_coll = cb.scope(catalog_scope).collection(catalog_col)

        click.secho(f"Uploading the {k} catalog items to Couchbase.", fg="yellow")
        logger.debug("Inserting catalog items...")
        progress_bar = tqdm.tqdm(catalog_desc.items)
        for item in progress_bar:
            try:
                key = item.identifier + "_" + metadata["version"]["identifier"]
                progress_bar.set_description(item.name)

                # serialise object to str
                item = json.dumps(item.model_dump(), cls=CustomPublishEncoder)

                # convert to dict object and insert snapshot id
                item_json: dict = json.loads(item)
                item_json.update({"catalog_identifier": metadata["version"]["identifier"]})

                # upsert docs to CB collection
                cb_coll.upsert(key, item_json)
            except CouchbaseException as e:
                click.secho(f"Couldn't insert catalog items!\n{e.message}", fg="red")
                return e
        click.secho(f"{k.capitalize()} catalog items successfully uploaded to Couchbase!\n", fg="green")

        # ---------------------------------------------------------------------------------------- #
        #                               GSI and Vector Indexes                                     #
        # ---------------------------------------------------------------------------------------- #
        click.secho(f"Now building the GSI indexes for the {k} catalog.", fg="yellow")
        s, err = create_gsi_indexes(bucket, cluster, k, True)
        if not s:
            raise ValueError(f"GSI indexes could not be created \n{err}")
        else:
            click.secho(f"All GSI indexes for the {k} catalog have been successfully created!\n", fg="green")
            logger.debug("Indexes created successfully!")

        click.secho(f"Now building the vector index for the {k} catalog.", fg="yellow")
        dims = len(catalog_desc.items[0].embedding)
        _, err = create_vector_index(bucket, k, connection_details_env, dims)
        if err is not None:
            raise ValueError(f"Vector index could not be created \n{err}")
        else:
            click.secho(f"Vector index for the {k} catalog has been successfully created!", fg="green")
            logger.debug("Vector index created successfully!")
        click.secho(DASHES, fg=KIND_COLORS[k])
