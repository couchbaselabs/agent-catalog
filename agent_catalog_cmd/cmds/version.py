import agent_catalog_core.catalog.version
import importlib.util

from ..models.context import Context


def cmd_version(ctx: Context):
    print(agent_catalog_core.catalog.version.lib_version())


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("version", __name__)

    @blueprint.route("/version")
    def route_version():
        return flask.jsonify(agent_catalog_core.catalog.version.lib_version())


if __name__ == "__main__":
    cmd_version({})
