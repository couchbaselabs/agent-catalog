import importlib.util

from libs.agent_catalog_libs.cmd.models.context import Context


def cmd_env(ctx: Context):
    print("activity: {}\ncatalog: {}\nverbose: {}".format(ctx.activity, ctx.catalog, ctx.verbose))


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("env", __name__)

    @blueprint.route("/env")
    def route_env():
        return flask.jsonify(flask.current_app.config["ctx"])
