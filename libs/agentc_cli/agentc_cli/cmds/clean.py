import click_extra
import couchbase.cluster
import importlib.util
import logging
import os
import pathlib
import shutil
import typing

from .util import logging_command
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_ACTIVITY_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.remote.util.query import execute_query
from typing_extensions import Literal

logger = logging.getLogger(__name__)


# TODO (GLENN): We should add some granularity w.r.t. what to clean here?
def clean_local(cfg: Config, targets: list[Literal["catalog", "activity"]]):
    target_folders = []
    if "catalog" in targets:
        target_folders.append(DEFAULT_CATALOG_FOLDER)
    if "activity" in targets:
        target_folders.append(DEFAULT_ACTIVITY_FOLDER)

    for folder in target_folders:
        if not folder or not os.path.exists(folder):
            continue
        folder_path = pathlib.Path(folder)
        if folder_path.is_file():
            os.remove(folder_path.absolute())
        elif folder_path.is_dir():
            shutil.rmtree(folder_path.absolute())


def clean_db(
    cfg: Config,
    catalog_ids: list[str],
    kind: list[typing.Literal["tool", "prompt"]],
    targets: list[Literal["catalog", "activity"]],
) -> int:
    cluster: couchbase.cluster.Cluster = cfg.Cluster()

    # TODO (GLENN): Is there a reason we are accumulating errors here (instead of stopping on the first error)?
    all_errs = list()
    if len(catalog_ids) > 0:
        for k in kind:
            click_extra.secho(f"Removing catalog(s): {[catalog for catalog in catalog_ids]}", fg="yellow")
            meta_catalog_condition = " AND ".join([f"version.identifier = '{catalog}'" for catalog in catalog_ids])
            remove_metadata_query = f"""
                DELETE FROM
                    `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{DEFAULT_CATALOG_METADATA_COLLECTION}
                WHERE
                    kind = "{k}" AND
                    {meta_catalog_condition};
            """
            res, err = execute_query(cluster, remove_metadata_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

            collection = DEFAULT_CATALOG_TOOL_COLLECTION if k == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
            catalog_condition = " AND ".join([f"catalog_identifier = '{catalog}'" for catalog in catalog_ids])
            remove_catalogs_query = f"""
                DELETE FROM
                    `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection}`
                WHERE
                    {catalog_condition};
            """
            res, err = execute_query(cluster, remove_catalogs_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

    else:
        if "catalog" in targets:
            drop_scope_query = f"DROP SCOPE `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

        if "activity" in targets:
            drop_scope_query = f"DROP SCOPE `{cfg.bucket}`.`{DEFAULT_ACTIVITY_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

        if len(all_errs) > 0:
            logger.error(all_errs)

    return len(all_errs)


@logging_command(logger)
def cmd_clean(
    cfg: Config = None,
    *,
    is_local: bool,
    is_db: bool,
    catalog_ids: tuple[str],
    kind: list[typing.Literal["tool", "prompt"]],
    targets: list[Literal["catalog", "activity"]],
):
    if cfg is None:
        cfg = Config()

    if is_local:
        clean_local(cfg, targets)
        click_extra.secho("Local FS catalog/metadata has been deleted!", fg="green")

    if is_db:
        num_errs = clean_db(cfg, catalog_ids, kind, targets)
        if num_errs > 0:
            raise ValueError("Failed to cleanup DB catalog/metadata!")
        else:
            click_extra.secho("Database catalog/metadata has been deleted!", fg="green")


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("clean", __name__)

    @blueprint.route("/clean", methods=["POST"])
    def route_clean():
        # TODO: Check creds as it's destructive.

        ctx = flask.current_app.config["ctx"]

        if True:  # TODO: Should check REST args on whether to clean local catalog.
            clean_local(ctx, None)

        # if False:  # TODO: Should check REST args on whether to clean db.
        #     clean_db(ctx, "TODO", None)

        return "OK"  # TODO.
