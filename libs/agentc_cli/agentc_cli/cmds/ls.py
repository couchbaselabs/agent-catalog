import click
import logging
import typing

from agentc_cli.cmds.util import DASHES
from agentc_cli.cmds.util import KIND_COLORS
from agentc_cli.cmds.util import get_catalog
from agentc_cli.cmds.util import logging_command
from agentc_core.catalog import CatalogBase
from agentc_core.config import Config

logger = logging.getLogger(__name__)


@logging_command(parent_logger=logger)
def cmd_ls(
    cfg: Config = None,
    *,
    kind: list[typing.Literal["tools", "prompts"]],
    include_dirty: bool,
    with_db: bool,
    with_local: bool,
):
    if cfg is None:
        cfg = Config()

    # TODO (GLENN): Clean this up later (right now there are mixed references to "tool" and "tools").
    kind = [k.removesuffix("s") for k in kind]

    # Determine what type of catalog we want.
    if with_local and with_db:
        force = "chain"
    elif with_db:
        force = "db"
    elif with_local:
        force = "local"
    else:
        raise ValueError("Either local FS or DB catalog must be specified!")

    # By default, we will only print the items line-by-line (and not anything extra).
    if cfg.verbosity_level == 0:
        for k in kind:
            catalog: CatalogBase = get_catalog(
                cfg, force=force, include_dirty=include_dirty, kind=k, printer=lambda x: None
            )
            for catalog_item in catalog:
                click.echo(f"{click.style(catalog_item.name, bold=True)}")

    # Otherwise, we will print the items with their descriptions (and with more format).
    else:
        for k in kind:
            click.secho(DASHES, fg=KIND_COLORS[k])
            click.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
            click.secho(DASHES, fg=KIND_COLORS[k])
            catalog: CatalogBase = get_catalog(cfg, force=force, include_dirty=include_dirty, kind=k)
            for i, catalog_item in enumerate(catalog):
                click.echo(f"{i+1}. {click.style(catalog_item.name, bold=True)}\n\t{catalog_item.description}")
            click.secho(DASHES, fg=KIND_COLORS[k])
