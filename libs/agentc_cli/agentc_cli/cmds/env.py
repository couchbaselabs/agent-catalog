import click
import importlib.util
import json
import re

from agentc_core.config import Config


def cmd_env(cfg: Config = None):
    if cfg is None:
        cfg = Config()
    for line in json.dumps(cfg.model_dump(), indent=4).split("\n"):
        if re.match(r'\s*"AGENT_CATALOG_.*": (?!null)', line):
            click.secho(line, fg="green")
        else:
            click.echo(line)


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("env", __name__)

    @blueprint.route("/env")
    def route_env():
        return flask.jsonify(flask.current_app.config["ctx"])
