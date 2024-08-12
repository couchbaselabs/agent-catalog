import os
import sys

import click
from dotenv import load_dotenv, find_dotenv

from .cmds import *
from .cmds.publish import cmd_publish
from ..core.utils.publish_utils import get_buckets, get_connection
from .models.publish.model import Keyspace, CouchbaseConnect
from .models.ctx.model import Context

# TODO: Should we load from ".env.rosetta"?
# TODO: Or, perhaps even stage specific, like from ".env.rosetta.prod"?
load_dotenv(find_dotenv(usecwd=True))


# Support abbreviated command aliases, ex: "rosetta st" ==> "rosetta status".
# From: https://click.palletsprojects.com/en/8.1.x/advanced/#command-aliases
class AliasedGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None

        if len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])

        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx, args):
        # Always return the full command name.
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args


@click.group(cls=AliasedGroup, epilog="See: https://docs.couchbase.com for more information.")
@click.option(
    "-c",
    "--catalog",
    default=".rosetta-catalog",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of local catalog files.
            The local catalog DIRECTORY should be checked into git.""",
    envvar="ROSETTA_CATALOG",
    show_default=True,
)
@click.option(
    "-a",
    "--activity",
    default=".rosetta-activity",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of local activity files (runtime data).
            The local activity DIRECTORY should NOT be checked into git,
            as it holds runtime activity data like logs, etc.""",
    envvar="ROSETTA_ACTIVITY",
    show_default=True,
)
@click.option(
    "-v", "--verbose", count=True, help="Enable verbose output.", envvar="ROSETTA_VERBOSE"
)
@click.pass_context
def click_main(ctx, catalog, activity, verbose):
    """A command line tool for Rosetta."""
    ctx.obj = Context(activity=activity, catalog=catalog, verbose=verbose)
    # ctx.obj = ctx.obj or {"catalog": catalog, "activity": activity, "verbose": verbose}


@click_main.command()
@click.pass_context
def clean(ctx):
    """Clean up catalog, activity, generated files, etc."""
    cmd_clean(ctx.obj)


@click_main.command()
@click.pass_context
def env(ctx):
    """Show this program's env or configuration parameters as JSON."""
    cmd_env(ctx.obj)


@click_main.command()
@click.argument("query", nargs=1)
@click.option(
    "--kind",
    default="tool",
    help="The kind of catalog to search.",
    show_default=True,
)
@click.option(
    "-k",
    "--top-k",
    default=1,
    help="The maximum number of results to show.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=True,
    help="Whether to consider and process dirty source files for the find query.",
    show_default=True,
)
@click.option(
    "--reranker",
    default="ClosestCluster",
    help="""Reranking of candidate results.
            Valid values: ClosestCluster, none.""",
    show_default=True,
)
@click.pass_context
def find(ctx, query, kind, top_k, include_dirty, reranker):
    """Find tools, prompts, etc.
       from the catalog based on a natural language QUERY string."""
    cmd_find(ctx.obj, query, kind=kind, top_k=top_k,
             include_dirty=include_dirty, reranker=reranker)


@click_main.command()
@click.argument("source_dirs", nargs=-1)
@click.option(
    "--kind",
    default="tool",
    help="The kind of items to index into the local catalog.",
    show_default=True,
)
@click.option(
    "-em",
    "--embedding-model",
    default=DEFAULT_EMBEDDING_MODEL,
    help="Embedding model when indexing source files into the local catalog.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=False,
    help="Whether to index dirty source files into the local catalog.",
    show_default=True,
)
@click.option(
    "--dry-run",
    default=False,
    help="When true, do not update the local catalog files.",
    show_default=True,
)
@click.pass_context
def index(ctx, source_dirs, kind, embedding_model, include_dirty, dry_run):
    """Walk source directory trees for indexing source files into the local catalog.

    SOURCE_DIRS defaults to "."

    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""

    if not source_dirs:
        source_dirs = ["."]

    # TODO: The index command should default to the '.' directory / current directory.
    # TODO: The index command should ignore the '.git' subdirectory.
    # TODO: The index command should ignore whatever's in the '.gitignore' file.

    cmd_index(ctx.obj, source_dirs=source_dirs, kind=kind, embedding_model=embedding_model,
              include_dirty=include_dirty, dry_run=dry_run)


@click_main.command()
@click.option(
    "-sc",
    "--scope",
    default="rosetta-catalog",
    help="Couchbase Scope where data is inserted.",
)
@click.pass_context
def publish(ctx, scope):
    """Publish the local catalog to a database."""

    keyspace_details = Keyspace(bucket="", scope=scope)
    connection_details = CouchbaseConnect(
        connection_url=os.getenv("CB_CONN_STRING"),
        username=os.getenv("CB_USERNAME"),
        password=os.getenv("CB_PASSWORD"),
    )

    # Establish a connection
    err, cluster = get_connection(conn=connection_details)
    if err:
        click.echo(str(err))
        return

    # Get buckets from CB Cluster
    buckets = get_buckets(cluster=cluster)

    # Prompt user to select a bucket
    selected_bucket = click.prompt(
        "Please select a bucket", type=click.Choice(buckets), show_choices=True
    )
    click.echo(f"Inserting documents in : {selected_bucket}/{keyspace_details.scope}\n")
    keyspace_details.bucket = selected_bucket

    # Publish catalog into keyspace
    msg = cmd_publish(ctx.obj, cluster=cluster, keyspace=keyspace_details)
    print(msg)

    # Close cluster connection
    cluster.close()


@click_main.command()
@click.option(
    "--kind",
    default="tool",
    help="The kind of catalog to show status.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=True,
    help="Whether to consider dirty source files for status.",
    show_default=True,
)
@click.pass_context
def status(ctx, kind, include_dirty):
    """Show the status of the local catalog."""
    cmd_status(ctx.obj, kind=kind, include_dirty=include_dirty)


@click_main.command()
@click.pass_context
def version(ctx):
    """Show the version of this tool."""
    cmd_version(ctx.obj)


@click_main.command()
@click.option(
    "--host-port",
    default=DEFAULT_WEB_HOST_PORT,
    envvar="ROSETTA_WEB_HOST_PORT",
    help="The host:port to listen on.",
    show_default=True,
)
@click.option(
    "--debug/--no-debug",
    envvar="ROSETTA_WEB_DEBUG",
    default=True,
    help="Debug mode.",
    show_default=True,
)
@click.pass_context
def web(ctx, host_port, debug):
    """Start local web server."""
    cmd_web(ctx.obj, host_port, debug)


def main():
    try:
        click_main()
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)

        if os.getenv("ROSETTA_DEBUG") is not None:
            # Set ROSETTA_DEBUG so standard python stack trace is emitted.
            raise (e)

        sys.exit(1)


if __name__ == "__main__":
    main()
