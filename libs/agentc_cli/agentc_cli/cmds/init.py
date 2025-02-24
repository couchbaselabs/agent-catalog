import agentc_core.defaults
import click
import contextlib
import couchbase.cluster
import couchbase.exceptions
import logging
import os
import pathlib
import typing

from .util import CATALOG_KINDS
from .util import logging_command
from agentc_core.analytics.create import create_analytics_views
from agentc_core.analytics.create import create_query_udfs
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from agentc_core.defaults import DEFAULT_AUDIT_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.util.ddl import create_gsi_indexes
from agentc_core.util.ddl import create_scope_and_collection
from agentc_core.util.ddl import create_vector_index

logger = logging.getLogger(__name__)


@logging_command(parent_logger=logger)
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
    bucket_manager = cb.collections()

    # ---------------------------------------------------------------------------------------- #
    #                               SCOPES and COLLECTIONS                                     #
    # ---------------------------------------------------------------------------------------- #
    (msg, err) = create_scope_and_collection(
        bucket_manager, scope=DEFAULT_CATALOG_SCOPE, collection=DEFAULT_CATALOG_METADATA_COLLECTION
    )
    if err is not None:
        raise ValueError(msg)
    else:
        click.secho("Metadata collection for the catalog has been successfully created!\n", fg="green")

    for kind in CATALOG_KINDS:
        # Create the catalog collection if it does not exist
        click.secho(f"Now creating the catalog collection for the {kind} catalog.", fg="yellow")
        catalog_col = DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
        (msg, err) = create_scope_and_collection(bucket_manager, scope=DEFAULT_CATALOG_SCOPE, collection=catalog_col)
        if err is not None:
            raise ValueError(msg)
        else:
            click.secho(f"Catalog collection for the {kind} catalog has been successfully created!\n", fg="green")

    # ---------------------------------------------------------------------------------------- #
    #                               GSI and Vector Indexes                                     #
    # ---------------------------------------------------------------------------------------- #
    embedding_model = EmbeddingModel(
        embedding_model_name=cfg.embedding_model_name,
        embedding_model_url=cfg.embedding_model_url,
        embedding_model_auth=cfg.embedding_model_auth,
        sentence_transformers_model_cache=cfg.sentence_transformers_model_cache,
    )
    dims = len(embedding_model.encode("test"))
    for kind in CATALOG_KINDS:
        click.secho(f"Now building the GSI indexes for the {kind} catalog.", fg="yellow")
        completion_status, err = create_gsi_indexes(cfg, kind, True)
        if not completion_status:
            raise ValueError(f"GSI indexes could not be created \n{err}")
        else:
            click.secho(f"All GSI indexes for the {kind} catalog have been successfully created!\n", fg="green")

        click.secho(f"Now building the vector index for the {kind} catalog.", fg="yellow")
        _, err = create_vector_index(
            cfg=cfg,
            scope=DEFAULT_CATALOG_SCOPE,
            collection=DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION,
            index_name=f"v1_agent_catalog_{kind}_index",
            dim=dims,
        )
        if err is not None:
            raise ValueError(f"Vector index could not be created \n{err}")
        else:
            click.secho(f"Vector index for the {kind} catalog has been successfully created!\n", fg="green")


def init_db_auditor(cfg: Config, cluster: couchbase.cluster.Cluster):
    # TODO (GLENN): This is misnamed? Should be a collection manager.
    cb: couchbase.cluster.Bucket = cluster.bucket(cfg.bucket)
    bucket_manager = cb.collections()

    # Create the scope and collection for the auditor.
    log_col = DEFAULT_ACTIVITY_LOG_COLLECTION
    log_scope = DEFAULT_AUDIT_SCOPE
    click.secho("Now creating scope and collections for the auditor.", fg="yellow")
    (msg, err) = create_scope_and_collection(bucket_manager, scope=log_scope, collection=log_col)
    if err is not None:
        raise ValueError(msg)
    else:
        click.secho("Scope and collection for the auditor have been successfully created!\n", fg="green")

    # Create our query UDFs for the auditor.
    click.secho("Now creating the query UDFs for the auditor.", fg="yellow")
    try:
        create_query_udfs(cluster, cfg.bucket)
        click.secho("All query UDFs for the auditor have been successfully created!\n", fg="green")
    except couchbase.exceptions.CouchbaseException as e:
        click.secho("Query UDFs could not be created.", fg="red")
        logger.warning("Query UDFs could not be created: %s", e)
        raise e

    # Create the analytics views for the auditor.
    click.secho("Now creating the analytics views for the auditor.", fg="yellow")
    try:
        create_analytics_views(cluster, cfg.bucket)
        click.secho("All analytics views for the auditor have been successfully created!\n", fg="green")
    except couchbase.exceptions.CouchbaseException as e:
        click.secho("Analytics views could not be created.", fg="red")
        logger.warning("Analytics views could not be created: %s", e)
        raise e
