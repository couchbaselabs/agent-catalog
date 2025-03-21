import click_extra
import couchbase.cluster
import logging
import pathlib
import typing

from .util import DASHES
from .util import KIND_COLORS
from .util import logging_command
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.remote.publish import publish_catalog
from agentc_core.remote.publish import publish_logs

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_publish(
    cfg: Config = None,
    *,
    kind: list[typing.Literal["tools", "prompts", "logs"]],
    annotations: list[dict] = None,
):
    """Command to publish catalog items to user's Couchbase cluster"""
    if cfg is None:
        cfg = Config()
    if annotations is None:
        annotations = list()

    # Connect to our bucket.
    cluster: couchbase.cluster.Cluster = cfg.Cluster()
    cb: couchbase.cluster.Bucket = cluster.bucket(cfg.bucket)

    # TODO (GLENN): Clean this up later (right now there are mixed references to "tool" and "tools").
    kind = [k.removesuffix("s") for k in kind]

    # Publish logs to cluster
    if "log" in kind:
        k = "log"
        click_extra.secho(DASHES, fg=KIND_COLORS[k])
        click_extra.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
        click_extra.secho(DASHES, fg=KIND_COLORS[k])
        log_path = pathlib.Path(cfg.activity_folder) / DEFAULT_ACTIVITY_FILE
        logger.debug("Local FS log path: ", log_path)
        log_messages = publish_logs(cb, log_path)
        click_extra.secho(f"Successfully upserted {len(log_messages)} local FS logs to cluster!")
        click_extra.secho(DASHES, fg=KIND_COLORS[k])

    # Publish tools and/or prompts
    for k in [_k for _k in kind if _k != "log"]:
        click_extra.secho(DASHES, fg=KIND_COLORS[k])
        click_extra.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
        click_extra.secho(DASHES, fg=KIND_COLORS[k])
        publish_catalog(cb, cfg, k, annotations, click_extra.secho)
        click_extra.secho(f"{k.capitalize()} catalog items successfully uploaded to Couchbase!\n", fg="green")
