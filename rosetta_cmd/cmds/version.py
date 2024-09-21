import flask
import rosetta_core.catalog.version

from ..models.context import Context

blueprint = flask.Blueprint("version", __name__)


@blueprint.route("/version")
def route_version():
    return flask.jsonify(rosetta_core.catalog.version.lib_version())


def cmd_version(ctx: Context):
    print(rosetta_core.catalog.version.lib_version())


if __name__ == "__main__":
    cmd_version({})
