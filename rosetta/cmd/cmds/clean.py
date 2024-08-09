import os
import pathlib
import shutil

import couchbase.auth
import flask

from ..models.ctx.model import Context


def clean_local(ctx: Context):
    xs = [
        ctx.activity,
        # TODO: We should instead glob for all *_catalog.json files?
        ctx.catalog + "/tool-catalog.json", # TODO: Temporary during refactoring.
        ctx.catalog + "/tool_catalog.json",
        ctx.catalog + "/prompt_catalog.json",
        ctx.catalog + "/meta.json",
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
