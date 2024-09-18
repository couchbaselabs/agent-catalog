import click
import flask
import logging
import os
import pathlib
import shutil

from ..defaults import DEFAULT_ACTIVITY_FOLDER
from ..defaults import DEFAULT_CATALOG_FOLDER
from ..defaults import DEFAULT_SCOPE_PREFIX
from ..models.context import Context
from rosetta_core.defaults import DEFAULT_AUDIT_SCOPE
from rosetta_util.query import execute_query

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


def clean_db(ctx, bucket, cluster, embedding_model):
    all_errs = []
    catalog_scope_name = DEFAULT_SCOPE_PREFIX + embedding_model.replace("/", "_")
    drop_scope_query = f"DROP SCOPE `{bucket}`.`{catalog_scope_name}` IF EXISTS;"
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

    if len(all_errs) == 0:
        click.secho("Successfully cleaned up db!", fg="green")
    else:
        logger.error(all_errs)


def cmd_clean(ctx, is_clean_local, is_clean_db, bucket, cluster, embedding_model):
    if is_clean_local:
        clean_local(ctx)

    if is_clean_db:
        clean_db(ctx, bucket, cluster, embedding_model)


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
