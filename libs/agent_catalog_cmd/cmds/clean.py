import click
import couchbase.cluster
import importlib.util
import logging
import os
import pathlib
import shutil

from ..defaults import DEFAULT_ACTIVITY_FOLDER
from ..defaults import DEFAULT_CATALOG_FOLDER
from ..defaults import DEFAULT_CATALOG_SCOPE
from ..models.context import Context
from agent_catalog_core.defaults import DEFAULT_AUDIT_SCOPE
from agent_catalog_util.query import execute_query

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


def clean_db(ctx, bucket, cluster) -> int:
    all_errs = []
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


def cmd_clean(ctx: Context, is_local: bool, is_db: bool, bucket: str, cluster: couchbase.cluster):
    if is_local:
        click.secho("Started cleaning local catalog....", fg="yellow")
        clean_local(ctx)
        click.secho("Successfully cleaned up local catalog!", fg="green")

    if is_db:
        click.secho("Started cleaning db catalog....", fg="yellow")
        num_errs = clean_db(ctx, bucket, cluster)
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
