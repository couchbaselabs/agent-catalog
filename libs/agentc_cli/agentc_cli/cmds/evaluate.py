import click
import logging
import os

from .util import logging_command
from agentc_core.config import Config
from agentc_core.evaluation import evaluate

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_evaluate(cfg: Config = None, *, source_dirs: list[str | os.PathLike], name_globs: list[str]):
    if cfg is None:
        cfg = Config()

    evaluate(source_dirs, name_globs=name_globs, printer=click.secho)
