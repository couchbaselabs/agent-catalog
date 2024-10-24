import click
import importlib.util
import json
import os
import re

from ..models.context import Context
from agentc_core.catalog import LATEST_SNAPSHOT_VERSION
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL


def cmd_env(ctx: Context):
    environment_dict = {
        "AGENT_CATALOG_ACTIVITY": ctx.activity,
        "AGENT_CATALOG_CATALOG": ctx.catalog,
        "AGENT_CATALOG_VERBOSE": ctx.verbose,
        "AGENT_CATALOG_INTERACTIVE": ctx.interactive,
        "AGENT_CATALOG_DEBUG": os.getenv("AGENT_CATALOG_DEBUG", False),
        "AGENT_CATALOG_CONN_STRING": os.getenv("AGENT_CATALOG_CONN_STRING"),
        "AGENT_CATALOG_USERNAME": os.getenv("AGENT_CATALOG_USERNAME"),
        "AGENT_CATALOG_PASSWORD": os.getenv("AGENT_CATALOG_PASSWORD"),
        "AGENT_CATALOG_BUCKET": os.getenv("AGENT_CATALOG_BUCKET"),
        "AGENT_CATALOG_SNAPSHOT": os.getenv("AGENT_CATALOG_SNAPSHOT", LATEST_SNAPSHOT_VERSION),
        "AGENT_CATALOG_PROVIDER_OUTPUT": os.getenv("AGENT_CATALOG_PROVIDER_OUTPUT", None),
        "AGENT_CATALOG_AUDITOR_OUTPUT": os.getenv("AGENT_CATALOG_AUDITOR_OUTPUT", None),
        "AGENT_CATALOG_EMBEDDING_MODEL": os.getenv("AGENT_CATALOG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
    }
    for line in json.dumps(environment_dict, indent=4).split("\n"):
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
