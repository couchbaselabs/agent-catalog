import click
import couchbase.cluster
import importlib.util
import logging
import os
import pathlib
import shutil
import typing

from ..models.context import Context
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_AUDIT_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.util.query import execute_query

logger = logging.getLogger(__name__)


def clean_local(ctx: Context | None):
    xs = [DEFAULT_ACTIVITY_FOLDER, DEFAULT_CATALOG_FOLDER]

    for x in xs:
        if not x or not os.path.exists(x):
            continue

        x_path = pathlib.Path(x)

        if x_path.is_file():
            os.remove(x_path.absolute())
        elif x_path.is_dir():
            shutil.rmtree(x_path.absolute())


def clean_db(
    ctx: Context | None,
    bucket: str,
    cluster: couchbase.cluster.Cluster,
    catalog_ids: list[str],
    kind_list: list[typing.Literal["tool", "prompt"]],
) -> int:
    all_errs = []

    for kind in kind_list:
        if len(catalog_ids) > 0:
            click.secho(f"Removing catalog(s): {[catalog for catalog in catalog_ids]}", fg="yellow")

            catalog_condition = " AND ".join([f"catalog_identifier = '{catalog}'" for catalog in catalog_ids])
            meta_catalog_condition = " AND ".join([f"version.identifier = '{catalog}'" for catalog in catalog_ids])
            remove_catalogs_query = f"""
                DELETE FROM
                    `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_CATALOG_COLLECTION_NAME}
                WHERE
                    {catalog_condition};
            """
            remove_metadata_query = f"""
                DELETE FROM
                    `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_META_COLLECTION_NAME}
                WHERE
                    {meta_catalog_condition};
            """

            res, err = execute_query(cluster, remove_catalogs_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

            res, err = execute_query(cluster, remove_metadata_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)
        else:
            drop_scope_query = f"DROP SCOPE `{bucket}`.`{DEFAULT_CATALOG_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

            drop_scope_query = f"DROP SCOPE `{bucket}`.`{DEFAULT_AUDIT_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

            if len(all_errs) > 0:
                logger.error(all_errs)

    return len(all_errs)


def cmd_clean(
    is_local: bool,
    is_db: bool,
    bucket: str,
    cluster: couchbase.cluster.Cluster,
    catalog_ids: tuple[str],
    kind: list[typing.Literal["tool", "prompt"]],
    ctx: Context = None,
):
    if is_local:
        clean_local(ctx)
        click.secho("Local catalog has been deleted!", fg="green")

    if is_db:
        num_errs = clean_db(ctx, bucket, cluster, catalog_ids, kind)
        if num_errs > 0:
            raise ValueError("Failed to cleanup db catalog!")
        else:
            click.secho("Database catalog has been deleted!", fg="green")


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

        if False:  # TODO: Should check REST args on whether to clean db.
            clean_db(ctx, "TODO", None)

        return "OK"  # TODO.
