import click
import couchbase.cluster
import typing

from agentc_cli.cmds.util import DASHES
from agentc_cli.cmds.util import KIND_COLORS
from agentc_cli.cmds.util import get_catalog
from agentc_cli.models import Context


def cmd_ls(
    ctx: Context,
    kind_list: list[typing.Literal["tool", "prompt"]],
    bucket: str = None,
    cluster: couchbase.cluster.Cluster = None,
    force_db=False,
):
    if ctx is None:
        ctx = Context()

    for kind in kind_list:
        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho(kind.upper(), bold=True, fg=KIND_COLORS[kind])
        click.secho(DASHES, fg=KIND_COLORS[kind])
        catalog = get_catalog(
            ctx.catalog, bucket=bucket, cluster=cluster, force_db=force_db, include_dirty=False, kind=kind
        )

        catalog_items = catalog.get_all_items()
        num = 1
        for catalog_item in catalog_items:
            click.echo(f"{num}. {click.style(catalog_item.name, bold=True)}\n\t{catalog_item.description}")
            num += 1

        click.secho(DASHES, fg=KIND_COLORS[kind])
