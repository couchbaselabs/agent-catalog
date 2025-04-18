import click_extra
import importlib.util
import logging

from .util import logging_command
from agentc_core.catalog import version as core_version
from agentc_core.config import Config

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_version(cfg: Config = None):
    if cfg is None:
        cfg = Config()
    click_extra.secho(core_version.lib_version(), bold=True)


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("version", __name__)

    @blueprint.route("/version")
    def route_version():
        return flask.jsonify(core_version.lib_version())


if __name__ == "__main__":
    cmd_version({})
