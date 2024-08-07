import flask
from ..models.ctx.model import Context

blueprint = flask.Blueprint("env", __name__)


@blueprint.route("/env")
def route_env():
    return flask.jsonify(flask.current_app.config["ctx"])


def cmd_env(ctx: Context):
    print("activity: {},\ncatalog: {},\nverbose: {}".format(ctx.activity, ctx.catalog, ctx.verbose))
    # print(json.dumps(ctx, sort_keys=True, indent=4))
