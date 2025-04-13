import agentc_core.defaults
import agentc_core.remote.init
import agentc_core.remote.util.ddl
import click_extra
import contextlib
import couchbase.cluster
import couchbase.exceptions
import logging
import os
import pathlib
import typing

from .util import CATALOG_KINDS
from .util import logging_command
from agentc_core.activity.remote.create import create_analytics_views
from agentc_core.activity.remote.create import create_query_udfs
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from agentc_core.defaults import DEFAULT_ACTIVITY_SCOPE
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.remote.init import init_analytics_collection
from agentc_core.remote.init import init_catalog_collection
from agentc_core.remote.init import init_metadata_collection
from agentc_core.remote.util.ddl import create_gsi_indexes
from agentc_core.remote.util.ddl import create_scope_and_collection

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_init(
    cfg: Config = None,
    *,
    targets: list[typing.Literal["catalog", "activity"]],
    db: bool = True,
    local: bool = True,
):
    if cfg is None:
        cfg = Config()

    if local:
        logger.debug("Initializing local-FS catalog and activity.")
        if "catalog" in targets:
            init_local_catalog(cfg)
        if "activity" in targets:
            init_local_activity(cfg)

    if db:
        logger.debug("Initializing DB catalog and activity.")
        cluster = cfg.Cluster()
        if "catalog" in targets:
            init_db_catalog(cfg, cluster)
        if "activity" in targets:
            init_db_auditor(cfg, cluster)
        cluster.close()


def init_local_catalog(cfg: Config):
    # Init directories.
    if cfg.catalog_path is not None:
        with contextlib.suppress(FileExistsError):
            os.mkdir(cfg.catalog_path)
    elif cfg.project_path is not None:
        with contextlib.suppress(FileExistsError):
            os.mkdir(cfg.project_path / agentc_core.defaults.DEFAULT_CATALOG_FOLDER)
    else:
        project_path = pathlib.Path.cwd()
        with contextlib.suppress(FileExistsError):
            os.mkdir(project_path / agentc_core.defaults.DEFAULT_CATALOG_FOLDER)
    with contextlib.suppress(FileExistsError):
        os.mkdir(DEFAULT_MODEL_CACHE_FOLDER)

    # We will also download our embedding model here.
    cfg.EmbeddingModel()._load()


def init_local_activity(cfg: Config):
    # Init directories.
    if cfg.activity_path is not None:
        with contextlib.suppress(FileExistsError):
            os.mkdir(cfg.activity_path)
    elif cfg.project_path is not None:
        with contextlib.suppress(FileExistsError):
            os.mkdir(cfg.project_path / agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER)
    else:
        project_path = pathlib.Path.cwd()
        with contextlib.suppress(FileExistsError):
            os.mkdir(project_path / agentc_core.defaults.DEFAULT_ACTIVITY_FOLDER)


def init_db_catalog(cfg: Config, cluster: couchbase.cluster.Cluster):
    # Get the bucket manager
    cb: couchbase.cluster.Bucket = cluster.bucket(cfg.bucket)
    collection_manager = cb.collections()
    logger.debug("Using bucket: %s", cfg.bucket)

    init_metadata_collection(collection_manager, cfg, click_extra.secho)
    dims = len(cfg.EmbeddingModel("NAME").encode("test"))
    for kind in CATALOG_KINDS:
        init_catalog_collection(collection_manager, cfg, kind, dims, click_extra.secho)

    # Create the analytics collections.
    click_extra.secho("Now creating the analytics collections for our catalog.", fg="yellow")
    try:
        init_analytics_collection(cluster, cfg.bucket)
        click_extra.secho("All analytics collections for the catalog have been successfully created!\n", fg="green")
    except couchbase.exceptions.CouchbaseException as e:
        click_extra.secho("Analytics collections could not be created.", fg="red")
        logger.warning("Analytics collections could not be created: %s", e)
        raise e


def init_db_auditor(cfg: Config, cluster: couchbase.cluster.Cluster):
    cb: couchbase.cluster.Bucket = cluster.bucket(cfg.bucket)
    bucket_manager = cb.collections()

    # Create the scope and collection for the auditor.
    log_col = DEFAULT_ACTIVITY_LOG_COLLECTION
    log_scope = DEFAULT_ACTIVITY_SCOPE
    click_extra.secho("Now creating scope and collections for the auditor.", fg="yellow")
    (msg, err) = create_scope_and_collection(
        bucket_manager,
        scope=log_scope,
        collection=log_col,
        ddl_retry_attempts=cfg.ddl_retry_attempts,
        ddl_retry_wait_seconds=cfg.ddl_retry_wait_seconds,
    )
    if err is not None:
        raise ValueError(msg)
    else:
        click_extra.secho("Scope and collection for the auditor have been successfully created!\n", fg="green")

    # Create the primary index for our logs collection.
    click_extra.secho("Now creating the primary index for the auditor.", fg="yellow")
    (completion_status, err) = create_gsi_indexes(cfg, "log", True)
    if err:
        raise ValueError(f"GSI index could not be created.\n{err}")
    else:
        click_extra.secho("Primary index for the auditor has been successfully created!\n", fg="green")

    # Create our query UDFs for the auditor.
    click_extra.secho("Now creating the query UDFs for the auditor.", fg="yellow")
    try:
        create_query_udfs(cluster, cfg.bucket)
        click_extra.secho("All query UDFs for the auditor have been successfully created!\n", fg="green")
    except couchbase.exceptions.CouchbaseException as e:
        click_extra.secho("Query UDFs could not be created.", fg="red")
        logger.warning("Query UDFs could not be created: %s", e)
        raise e

    # Create the analytics views for the auditor.
    click_extra.secho("Now creating the analytics views for the auditor.", fg="yellow")
    try:
        create_analytics_views(cluster, cfg.bucket)
        click_extra.secho("All analytics views for the auditor have been successfully created!\n", fg="green")
    except couchbase.exceptions.CouchbaseException as e:
        click_extra.secho("Analytics views could not be created.", fg="red")
        logger.warning("Analytics views could not be created: %s", e)
        raise e
