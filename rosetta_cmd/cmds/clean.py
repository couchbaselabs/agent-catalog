import couchbase.auth
import flask
import os
import pathlib
import shutil

from ..defaults import DEFAULT_META_CATALOG_NAME
from ..defaults import DEFAULT_PROMPT_CATALOG_NAME
from ..defaults import DEFAULT_TOOL_CATALOG_NAME
from ..models.context import Context


def clean_local(ctx: Context):
    xs = [
        ctx.activity,
        # TODO: We should instead glob for all *_catalog.json files?
        ctx.catalog + "/" + DEFAULT_TOOL_CATALOG_NAME,
        ctx.catalog + "/" + DEFAULT_PROMPT_CATALOG_NAME,
        ctx.catalog + "/" + DEFAULT_META_CATALOG_NAME,
    ]

    for x in xs:
        if not x or not os.path.exists(x):
            continue

        x_path = pathlib.Path(x)

        if x_path.is_file():
            os.remove(x_path.absolute())
        elif x_path.is_dir():
            shutil.rmtree(x_path.absolute())


# TODO: Implement clean for the rosetta scope in Couchbase.
def clean_db(ctx, conn_string: str, authenticator: couchbase.auth.Authenticator, **_):
    pass


def cmd_clean(ctx):
    if True:  # TODO: Should check cmd-line flags on whether to clean local catalog.
        clean_local(ctx)

    if False:  # TODO: Should check cmd-line flags on whether to clean db.
        clean_db(ctx, "TODO", None)


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
