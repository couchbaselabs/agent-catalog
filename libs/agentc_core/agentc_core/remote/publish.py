import couchbase.cluster
import couchbase.exceptions
import datetime
import json
import logging
import pathlib
import pydantic
import tqdm
import typing
import uuid

from agentc_core.activity.models.log import Log
from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from agentc_core.defaults import DEFAULT_ACTIVITY_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_core.record.descriptor import RecordKind
from agentc_core.remote.util.ddl import check_if_scope_collection_exist

logger = logging.getLogger(__name__)


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, pathlib.Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)


def publish_logs(cb: couchbase.cluster.Bucket, log_path: pathlib.Path):
    log_messages = []
    try:
        with log_path.open("r") as fp:
            for line in fp:
                try:
                    log_messages.append(Log.model_validate_json(line.strip()))
                except pydantic.ValidationError as e:
                    logger.warning(
                        f"Invalid log entry encountered!\n"
                        f"Read malformed log entry: {line}\n"
                        f"Swallowing exception {e}."
                    )
        logger.debug(len(log_messages), "logs found..\n")
    except FileNotFoundError as e:
        raise ValueError("No log file found! Please run generate activity using the auditor!") from e
    # Connect to our log collection.
    bucket_manager = cb.collections()
    check_if_scope_collection_exist(bucket_manager, DEFAULT_ACTIVITY_SCOPE, DEFAULT_ACTIVITY_LOG_COLLECTION, True)
    cb_coll = cb.scope(DEFAULT_ACTIVITY_SCOPE).collection(DEFAULT_ACTIVITY_LOG_COLLECTION)
    logger.debug("Upserting logs into the cluster.")
    for msg in log_messages:
        try:
            msg_str = msg.model_dump_json()
            msg_dict = json.loads(msg_str)
            key = msg_dict["identifier"]
            cb_coll.upsert(key, msg_dict)
        except couchbase.exceptions.CouchbaseException as e:
            raise ValueError(f"Couldn't insert log!\n{e.message}") from e
    return log_messages


def publish_catalog(
    cb: couchbase.cluster.Bucket,
    cfg: Config,
    k: typing.Literal["tool", "prompt"],
    annotations: list[dict],
    printer: typing.Callable = print,
):
    # Grab the local catalog.
    if k == "tool":
        catalog_path = cfg.CatalogPath() / DEFAULT_TOOL_CATALOG_FILE
    else:
        catalog_path = cfg.CatalogPath() / DEFAULT_PROMPT_CATALOG_FILE
    with catalog_path.open("r") as fp:
        catalog_desc = CatalogDescriptor.model_validate_json(fp.read())

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
    check_if_scope_collection_exist(bucket_manager, DEFAULT_CATALOG_SCOPE, DEFAULT_CATALOG_METADATA_COLLECTION, True)
    # get collection ref
    cb_coll = cb.scope(DEFAULT_CATALOG_SCOPE).collection(DEFAULT_CATALOG_METADATA_COLLECTION)
    # dict to store all the metadata - snapshot related data
    metadata = {el: catalog_desc.model_dump()[el] for el in catalog_desc.model_dump() if el != "items"}
    # add annotations to metadata
    annotations_list = {an[0]: an[1].split("+") if "+" in an[1] else an[1] for an in annotations}
    metadata.update({"snapshot_annotations": annotations_list})
    metadata["version"]["timestamp"] = str(metadata["version"]["timestamp"])
    logger.debug(f"Now processing the metadata for the {k} catalog.")
    try:
        key = f'{metadata["version"]["identifier"]}/{metadata["kind"]}'
        cb_coll.upsert(key, metadata)
    except couchbase.exceptions.CouchbaseException as e:
        raise ValueError(f"Couldn't insert metadata!\n{e.message}") from e
    printer("Using the catalog identifier: ", nl=False)
    printer(metadata["version"]["identifier"] + "\n", bold=True)

    # ---------------------------------------------------------------------------------------- #
    #                               Catalog items collection                                   #
    # ---------------------------------------------------------------------------------------- #
    catalog_col = DEFAULT_CATALOG_TOOL_COLLECTION if k == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
    check_if_scope_collection_exist(bucket_manager, DEFAULT_CATALOG_SCOPE, catalog_col, True)
    # get collection ref
    cb_coll = cb.scope(DEFAULT_CATALOG_SCOPE).collection(catalog_col)
    printer(f"Uploading the {k} catalog items to Couchbase.", fg="yellow")
    logger.debug("Inserting catalog items...")
    progress_bar = tqdm.tqdm(catalog_desc.items)
    for item in progress_bar:
        if (
            k == "prompt"
            and item.record_kind != RecordKind.Prompt
            or k == "tool"
            and item.record_kind == RecordKind.Prompt
        ):
            # If we reach here, then something went wrong during the indexing process.
            raise ValueError(f"Invalid record kind for {k} catalog item!\n{item.record_kind}")

        try:
            key = uuid.uuid4().hex
            progress_bar.set_description(item.name)

            # serialise object to str
            item = json.dumps(item.model_dump(), cls=CustomPublishEncoder)

            # convert to dict object and insert snapshot id
            item_json: dict = json.loads(item)
            item_json.update({"catalog_identifier": metadata["version"]["identifier"]})

            # upsert docs to CB collection
            cb_coll.upsert(key, item_json)
        except couchbase.exceptions.CouchbaseException as e:
            printer(f"Couldn't insert catalog items!\n{e.message}", fg="red")
            raise e
