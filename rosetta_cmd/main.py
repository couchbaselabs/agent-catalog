import click
import dotenv
import logging
import os
import sys

from .cmds import cmd_clean
from .cmds import cmd_env
from .cmds import cmd_find
from .cmds import cmd_index
from .cmds import cmd_publish
from .cmds import cmd_status
from .cmds import cmd_version
from .cmds import cmd_web
from .defaults import DEFAULT_ACTIVITY_FOLDER
from .defaults import DEFAULT_CATALOG_FOLDER
from .defaults import DEFAULT_EMBEDDING_MODEL
from .defaults import DEFAULT_SCOPE_PREFIX
from .defaults import DEFAULT_WEB_HOST_PORT
from .models import Context
from .models import CouchbaseConnect
from .models import Keyspace
from rosetta_util.publish import get_buckets
from rosetta_util.publish import get_connection

# Configure all logging here before we continue with our imports.
# By default, we won't print any log messages below WARNING.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

# Keeping this here, the logging these libraries do can be pretty verbose.
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("openapi_parser").setLevel(logging.ERROR)

# TODO: Should we load from ".env.rosetta"?
# TODO: Or, perhaps even stage specific, like from ".env.rosetta.prod"?
dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))


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
    default=DEFAULT_CATALOG_FOLDER,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of local catalog files.
            The local catalog DIRECTORY should be checked into git.""",
    envvar="ROSETTA_CATALOG",
    show_default=True,
)
@click.option(
    "-a",
    "--activity",
    default=DEFAULT_ACTIVITY_FOLDER,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of local activity files (runtime data).
            The local activity DIRECTORY should NOT be checked into git,
            as it holds runtime activity data like logs, etc.""",
    envvar="ROSETTA_ACTIVITY",
    show_default=True,
)
@click.option("-v", "--verbose", count=True, help="Enable verbose output.", envvar="ROSETTA_VERBOSE")
@click.pass_context
def click_main(ctx, catalog, activity, verbose):
    """A command line tool for Rosetta."""
    ctx.obj = Context(activity=activity, catalog=catalog, verbose=verbose)
    # ctx.obj = ctx.obj or {"catalog": catalog, "activity": activity, "verbose": verbose}


@click_main.command()
@click.pass_context
def clean(ctx):
    """Clean up the catalog folder, the activity folder, any generated files, etc..."""
    cmd_clean(ctx.obj)


@click_main.command()
@click.pass_context
def env(ctx):
    """Show this program's environment or configuration parameters as a JSON object."""
    cmd_env(ctx.obj)


@click_main.command()
@click.option(
    "--query",
    default="",
    help="User query describing the task for which tools / prompts are needed. This field or --name must be specified.",
    show_default=False,
)
@click.option(
    "--name",
    default="",
    help="Name of catalog item to retrieve from the catalog directly. This field or --query must be specified.",
    show_default=False,
)
@click.option(
    "--kind",
    default="tool",
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
    help="The kind of catalog to search.",
    show_default=True,
)
@click.option(
    "--bucket",
    default="",
    type=str,
    help="The name of the Couchbase bucket to search.",
    show_default=False,
)
@click.option(
    "--limit",
    default=1,
    help="The maximum number of results to show.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=True,
    is_flag=True,
    help="Whether to consider and process dirty source files for the find query.",
    show_default=True,
)
@click.option(
    "--refiner",
    type=click.Choice(["ClosestCluster", "None"], case_sensitive=False),
    default=None,
    help="Specify how to post-process find results.",
    show_default=True,
)
@click.option(
    "-an",
    "--annotations",
    type=str,
    default=None,
    help='Tool-specific annotations to filter by, specified using KEY="VALUE" (AND|OR KEY="VALUE")*.',
    show_default=True,
)
@click.option(
    "--search-db",
    default=False,
    is_flag=True,
    help="Enable this flag to perform DB level search.",
    show_default=True,
)
@click.option(
    "-em",
    "--embedding-model",
    default=DEFAULT_EMBEDDING_MODEL,
    help="Embedding model to generate embeddings for query.",
    show_default=True,
)
@click.pass_context
def find(ctx, query, name, kind, bucket, limit, include_dirty, refiner, annotations, search_db, embedding_model):
    """Find tools, prompts, etc. from the catalog based on a natural language QUERY string."""

    if search_db:
        # Load all Couchbase connection related data from env
        connection_details_env = CouchbaseConnect(
            connection_url=os.getenv("CB_CONN_STRING"),
            username=os.getenv("CB_USERNAME"),
            password=os.getenv("CB_PASSWORD"),
        )

        # Establish a connection
        err, cluster = get_connection(conn=connection_details_env)
        if err:
            click.echo(str(err))
            return

        # Get buckets from CB Cluster
        buckets = get_buckets(cluster=cluster)

        if bucket is None:
            # Prompt user to select a bucket
            bucket = click.prompt("Please select a bucket", type=click.Choice(buckets), show_choices=True)
        elif bucket not in buckets:
            raise ValueError("Bucket does not exist! The buckets available are: " + ",".join(buckets))

        cmd_find(
            ctx.obj,
            query=query,
            name=name,
            kind=kind,
            limit=limit,
            include_dirty=include_dirty,
            refiner=refiner,
            annotations=annotations,
            bucket=bucket,
            cluster=cluster,
            embedding_model=embedding_model,
        )
        cluster.close()
    else:
        cmd_find(
            ctx.obj,
            query=query,
            name=name,
            kind=kind,
            limit=limit,
            include_dirty=include_dirty,
            refiner=refiner,
            annotations=annotations,
            embedding_model=embedding_model,
        )


@click_main.command()
@click.argument("source_dirs", nargs=-1)
@click.option(
    "--kind",
    default="tool",
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
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
    is_flag=True,
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
    """Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
    SOURCE_DIRS defaults to ".", the current working directory.
    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""

    if not source_dirs:
        source_dirs = ["."]

    # TODO: The index command should default to the '.' directory / current directory.
    # TODO: The index command should ignore the '.git' subdirectory.
    # TODO: The index command should ignore whatever's in the '.gitignore' file.

    cmd_index(
        ctx.obj,
        source_dirs=source_dirs,
        kind=kind,
        embedding_model=embedding_model,
        include_dirty=include_dirty,
        dry_run=dry_run,
    )


@click_main.command()
@click.option(
    "--kind",
    default="all",
    type=click.Choice(["tool", "prompt", "all"], case_sensitive=False),
    help="The kind of catalog to insert into DB.",
    show_default=True,
)
@click.option(
    "--bucket",
    default="",
    type=str,
    help="The name of the Couchbase bucket to publish to.",
    show_default=False,
)
@click.option(
    "-an",
    "--annotations",
    multiple=True,
    type=click.Tuple([str, str]),
    default=[],
    help="Snapshot level annotations to be added while publishing.",
    show_default=True,
)
@click.pass_context
def publish(ctx, kind, bucket, annotations):
    """Publish the local catalog to Couchbase DB"""

    # Get keyspace and connection details
    keyspace_details = Keyspace(bucket="", scope=DEFAULT_SCOPE_PREFIX)

    # Load all Couchbase connection related data from env
    connection_details_env = CouchbaseConnect(
        connection_url=os.getenv("CB_CONN_STRING"),
        username=os.getenv("CB_USERNAME"),
        password=os.getenv("CB_PASSWORD"),
    )

    # Establish a connection
    err, cluster = get_connection(conn=connection_details_env)
    if err:
        click.echo(str(err))
        return

    # Get buckets from CB Cluster
    buckets = get_buckets(cluster=cluster)
    if bucket is None:
        # Prompt user to select a bucket
        bucket = click.prompt("Please select a bucket", type=click.Choice(buckets), show_choices=True)
    elif bucket not in buckets:
        raise ValueError("Bucket does not exist! The buckets available are: " + ",".join(buckets))

    click.echo(f"Inserting documents in : {bucket}/{keyspace_details.scope}\n")
    keyspace_details.bucket = bucket
    cmd_publish(ctx.obj, kind, annotations, cluster, keyspace_details, click.echo, connection_details_env)
    cluster.close()


@click_main.command()
@click.option(
    "--kind",
    default="tool",
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
    help="The kind of catalog to show status.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=True,
    is_flag=True,
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
    """Start a local web server to view our tools."""
    cmd_web(ctx.obj, host_port, debug)


def main():
    try:
        click_main()
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)

        if os.getenv("ROSETTA_DEBUG") is not None:
            # Set ROSETTA_DEBUG so standard python stack trace is emitted.
            raise e

        sys.exit(1)


if __name__ == "__main__":
    main()
