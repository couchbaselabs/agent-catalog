import click
import typing

from agentc_cli.cmds.util import DASHES
from agentc_cli.cmds.util import KIND_COLORS
from agentc_cli.cmds.util import get_catalog
from agentc_core.catalog import CatalogBase
from agentc_core.config import Config


def cmd_ls(
    cfg: Config = None,
    *,
    kind: list[typing.Literal["tool", "model-input"]],
    include_dirty: bool,
    with_db: bool,
    with_local: bool,
):
    if cfg is None:
        cfg = Config()

    # Determine what type of catalog we want.
    if with_local and with_db:
        force = "chain"
    elif with_db:
        force = "db"
    elif with_local:
        force = "local"
    else:
        raise ValueError("Either local FS or DB catalog must be specified!")

    for k in kind:
        click.secho(DASHES, fg=KIND_COLORS[k])
        click.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
        click.secho(DASHES, fg=KIND_COLORS[k])
        catalog: CatalogBase = get_catalog(
            catalog_path=cfg.CatalogPath(),
            bucket=cfg.bucket,
            cluster=cfg.Cluster() if with_db else None,
            force=force,
            include_dirty=include_dirty,
            kind=k,
        )

        catalog_items = list(catalog)
        num = 1
        for catalog_item in catalog_items:
            click.echo(f"{num}. {click.style(catalog_item.name, bold=True)}\n\t{catalog_item.description}")
            num += 1

        click.secho(DASHES, fg=KIND_COLORS[k])
