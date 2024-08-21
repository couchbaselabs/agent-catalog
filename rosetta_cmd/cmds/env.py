import flask

from ..models.context import Context

blueprint = flask.Blueprint("env", __name__)


@blueprint.route("/env")
def route_env():
    return flask.jsonify(flask.current_app.config["ctx"])


def cmd_env(ctx: Context):
    print("activity: {}\ncatalog: {}\nverbose: {}".format(ctx.activity, ctx.catalog, ctx.verbose))
