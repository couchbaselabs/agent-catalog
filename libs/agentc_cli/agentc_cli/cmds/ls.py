import click
import typing

from agentc_cli.cmds.util import DASHES
from agentc_cli.cmds.util import KIND_COLORS
from agentc_cli.cmds.util import get_catalog
from agentc_cli.models import Context


def cmd_ls(
    ctx: Context,
    kind: list[typing.Literal["tool", "prompt"]],
):
    if ctx is None:
        ctx = Context()

    for k in kind:
        click.secho(DASHES, fg=KIND_COLORS[k])
        click.secho(k.upper(), bold=True, fg=KIND_COLORS[k])
        click.secho(DASHES, fg=KIND_COLORS[k])
        catalog = get_catalog(ctx.catalog, bucket=None, cluster=None, force_db=False, include_dirty=False, kind=k)

        catalog_items = catalog.get_all_items()
        num = 1
        for catalog_item in catalog_items:
            click.echo(f"{num}. {click.style(catalog_item.name, bold=True)}\n\t{catalog_item.description}")
            num += 1

        click.secho(DASHES, fg=KIND_COLORS[k])
