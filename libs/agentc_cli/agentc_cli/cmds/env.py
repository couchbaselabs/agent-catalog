import click_extra
import importlib.util
import json
import logging
import re

from .util import logging_command
from agentc_core.config import Config

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_env(cfg: Config = None):
    if cfg is None:
        cfg = Config()
    for line in json.dumps(cfg.model_dump(), indent=4).split("\n"):
        if re.match(r'\s*"AGENT_CATALOG_.*": (?!null)', line):
            click_extra.secho(line, fg="green")
        else:
            click_extra.echo(line)


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("env", __name__)

    @blueprint.route("/env")
    def route_env():
        return flask.jsonify(flask.current_app.config["ctx"])
