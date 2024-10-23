import click
import couchbase.cluster
import importlib.util
import logging
import os
import pathlib
import shutil

from ..models.context import Context
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_AUDIT_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.util.query import execute_query

logger = logging.getLogger(__name__)


def clean_local(ctx: Context):
    xs = [DEFAULT_ACTIVITY_FOLDER, DEFAULT_CATALOG_FOLDER]

    for x in xs:
        if not x or not os.path.exists(x):
            continue

        x_path = pathlib.Path(x)

        if x_path.is_file():
            os.remove(x_path.absolute())
        elif x_path.is_dir():
            shutil.rmtree(x_path.absolute())


def clean_db(ctx, bucket, cluster, catalog_id, kind) -> int:
    all_errs = []

    if catalog_id is not None:
        click.secho(f"Removing catalog(s): {[catalog for catalog in catalog_id]}", fg="yellow")

        catalog_condition = ""
        meta_catalog_condition = ""
        for catalog in range(len(catalog_id) - 1):
            catalog_condition += f"catalog_identifier = '{catalog_id[catalog]}' AND "
            meta_catalog_condition += f"version.identifier = '{catalog_id[catalog]}' AND "
        catalog_condition += f"catalog_identifier = '{catalog_id[-1]}'"
        meta_catalog_condition += f"version.identifier = '{catalog_id[-1]}'"

        remove_catalogs_query = f"DELETE FROM `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_CATALOG_COLLECTION_NAME} WHERE {catalog_condition};"
        remove_metadata_query = f"DELETE FROM `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_META_COLLECTION_NAME} WHERE {meta_catalog_condition};"

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
    ctx: Context, is_local: bool, is_db: bool, bucket: str, cluster: couchbase.cluster, catalog_id: tuple, kind: str
):
    if is_local:
        click.secho("Started cleaning local catalog....", fg="yellow")
        clean_local(ctx)
        click.secho("Successfully cleaned up local catalog!", fg="green")

    if is_db:
        click.secho("Started cleaning db catalog....", fg="yellow")
        num_errs = clean_db(ctx, bucket, cluster, catalog_id, kind)
        if num_errs > 0:
            click.secho("ERROR: Failed to cleanup db catalog!", fg="red")
        else:
            click.secho("Successfully cleaned up db catalog!", fg="green")


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
