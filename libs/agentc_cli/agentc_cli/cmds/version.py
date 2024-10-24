import click
import importlib.util

from ..models.context import Context
from agentc_core.catalog import version as core_version


def cmd_version(ctx: Context):
    click.secho(core_version.lib_version(), bold=True)


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("version", __name__)

    @blueprint.route("/version")
    def route_version():
        return flask.jsonify(core_version.lib_version())


if __name__ == "__main__":
    cmd_version({})
