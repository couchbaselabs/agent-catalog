import couchbase.management.collections
import logging
import typing

from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.remote.util.ddl import create_gsi_indexes
from agentc_core.remote.util.ddl import create_scope_and_collection
from agentc_core.remote.util.ddl import create_vector_index

logger = logging.getLogger(__name__)


def init_metadata_collection(
    collection_manager: couchbase.management.collections.CollectionManager,
    cfg: Config,
    printer: typing.Callable = print,
):
    logger.info("Starting metadata collection initialization.")
    (msg, err) = create_scope_and_collection(
        collection_manager, scope=DEFAULT_CATALOG_SCOPE, collection=DEFAULT_CATALOG_METADATA_COLLECTION
    )
    if err is not None:
        raise ValueError(msg)
    else:
        printer("Metadata scope and collection have been successfully created!\n", fg="green")

    completion_status, err = create_gsi_indexes(cfg, "metadata", True)
    if not completion_status:
        raise ValueError(f"GSI metadata index could not be created \n{err}")
    else:
        printer("GSI metadata index for the has been successfully created!\n", fg="green")


def init_catalog_collection(
    collection_manager: couchbase.management.collections.CollectionManager,
    cfg: Config,
    kind: typing.Literal["tool", "prompt"],
    dims: int,
    printer: typing.Callable = print,
):
    logger.info("Starting %s collection initialization.", kind + "s")
    printer(f"Now creating the catalog collection for the {kind} catalog.", fg="yellow")
    catalog_col = DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
    (msg, err) = create_scope_and_collection(collection_manager, scope=DEFAULT_CATALOG_SCOPE, collection=catalog_col)
    if err is not None:
        raise ValueError(msg)
    else:
        printer(f"Catalog collection for the {kind} catalog has been successfully created!\n", fg="green")

    printer(f"Now building the GSI indexes for the {kind} catalog.", fg="yellow")
    completion_status, err = create_gsi_indexes(cfg, kind, True)
    if not completion_status:
        raise ValueError(f"GSI indexes could not be created \n{err}")
    else:
        printer(f"All GSI indexes for the {kind} catalog have been successfully created!\n", fg="green")

    printer(f"Now building the vector index for the {kind} catalog.", fg="yellow")
    _, err = create_vector_index(
        cfg=cfg,
        scope=DEFAULT_CATALOG_SCOPE,
        collection=DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION,
        index_name=f"v2_AgentCatalog{kind.capitalize()}sEmbeddingIndex",
        dim=dims,
    )
    if err is not None:
        raise ValueError(f"Vector index could not be created \n{err}")
    else:
        printer(f"Vector index for the {kind} catalog has been successfully created!\n", fg="green")
