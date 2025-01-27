import click
import dotenv
import logging
import os
import pathlib
import pydantic
import sys
import textwrap

from .cmds import cmd_add
from .cmds import cmd_clean
from .cmds import cmd_env
from .cmds import cmd_execute
from .cmds import cmd_find
from .cmds import cmd_index
from .cmds import cmd_init
from .cmds import cmd_ls
from .cmds import cmd_publish
from .cmds import cmd_status
from .cmds import cmd_version
from .models import Context
from agentc_core.catalog import LATEST_SNAPSHOT_VERSION
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.defaults import DEFAULT_VERBOSITY_LEVEL
from agentc_core.record.descriptor import RecordKind
from agentc_core.util.connection import get_host_name
from agentc_core.util.models import CouchbaseConnect
from agentc_core.util.models import Keyspace
from agentc_core.util.publish import get_buckets
from agentc_core.util.publish import get_connection
from pydantic import ValidationError

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


# Support abbreviated command aliases, ex: "agentc st" ==> "agentc status".
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


@click.group(
    cls=AliasedGroup,
    epilog="See: https://docs.couchbase.com or https://couchbaselabs.github.io/agent-catalog/index.html# for more information.",
    context_settings=dict(max_content_width=800),
)
@click.option(
    "-c",
    "--catalog",
    default=DEFAULT_CATALOG_FOLDER,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of the local catalog files.""",
    envvar="AGENT_CATALOG_CATALOG",
    show_default=True,
)
@click.option(
    "-a",
    "--activity",
    default=DEFAULT_ACTIVITY_FOLDER,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="""Directory of the local activity files (runtime data).""",
    envvar="AGENT_CATALOG_ACTIVITY",
    show_default=True,
)
@click.option(
    "-v",
    "--verbose",
    default=DEFAULT_VERBOSITY_LEVEL,
    type=click.IntRange(min=0, max=2, clamp=True),
    count=True,
    help="Flag to enable verbose output.",
    envvar="AGENT_CATALOG_VERBOSE",
    show_default=True,
)
@click.option(
    "-i/-ni",
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Flag to enable interactive mode.",
    envvar="AGENT_CATALOG_INTERACTIVE",
    show_default=True,
)
@click.pass_context
def click_main(ctx, catalog, activity, verbose, interactive):
    """The Couchbase Agent Catalog command line tool."""
    ctx.obj = Context(activity=activity, catalog=catalog, verbose=verbose, interactive=interactive)


@click_main.command()
@click.pass_context
@click.argument(
    "catalog_type",
    type=click.Choice(["local", "db"], case_sensitive=False),
    nargs=-1,
)
@click.argument(
    "type_metadata",
    type=click.Choice(["catalog", "auditor", "all"], case_sensitive=False),
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to initialize in.",
    show_default=False,
)
def init(ctx, catalog_type, type_metadata, bucket):
    """Initialize the necessary files/collections for local/database catalog."""
    ctx_obj: Context = ctx.obj

    if not catalog_type:
        catalog_type = ["local", "db"]

    type_metadata = ["catalog", "auditor"] if type_metadata == "all" else [type_metadata]

    connection_details_env = None
    keyspace_details = None

    if "db" in catalog_type:
        # Load all Couchbase connection related data from env
        connection_details_env = CouchbaseConnect(
            connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
            username=os.getenv("AGENT_CATALOG_USERNAME"),
            password=os.getenv("AGENT_CATALOG_PASSWORD"),
            host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
            certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
        )

        # Establish a connection
        err, cluster = get_connection(conn=connection_details_env)
        if err:
            raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        # Determine the bucket.
        buckets = get_buckets(cluster=cluster)
        cluster.close()
        if bucket is None and ctx_obj.interactive:
            bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

        elif bucket is not None and bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\n"
                f"Run agentc publish --help for more information."
            )

        elif bucket is None and not ctx_obj.interactive:
            raise ValueError(
                "Bucket must be specified to publish to the database catalog."
                "Add --bucket BUCKET_NAME to your command or run agentc clean in interactive mode."
            )

        # Get keyspace and connection details
        keyspace_details = Keyspace(bucket=bucket, scope=DEFAULT_CATALOG_SCOPE)

    cmd_init(
        ctx=ctx_obj,
        catalog_type=catalog_type,
        type_metadata=type_metadata,
        connection_details_env=connection_details_env,
        keyspace_details=keyspace_details,
    )


@click_main.command()
@click.option(
    "-o",
    "--output",
    default=os.getcwd(),
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=pathlib.Path),
    help="Location to save the generated tool / prompt to. Defaults to your current working directory.",
)
@click.option(
    "--record-kind", type=click.Choice([c for c in RecordKind], case_sensitive=False), default=None, show_default=True
)
@click.pass_context
def add(ctx, output: pathlib.Path, record_kind: RecordKind):
    """Interactively create a new tool or prompt and save it to the filesystem (output)."""
    ctx_obj: Context = ctx.obj
    if not ctx_obj.interactive:
        click.secho(
            "ERROR: Cannot run agentc add in non-interactive mode! "
            "Specify your command without the non-interactive flag. ",
            fg="red",
        )
        return

    if record_kind is None:
        record_kind = click.prompt("Record Kind", type=click.Choice([c for c in RecordKind], case_sensitive=False))
    cmd_add(ctx=ctx_obj, output=output, record_kind=record_kind)


@click_main.command()
@click.argument(
    "catalog",
    type=click.Choice(["local", "db"], case_sensitive=False),
    nargs=-1,
)
@click.argument(
    "type_metadata",
    type=click.Choice(["catalog", "activity", "all"], case_sensitive=False),
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to remove agent-catalog from.",
    show_default=False,
)
@click.option(
    "-cid",
    "--catalog-id",
    multiple=True,
    default=None,
    type=str,
    help="Catalog ID used to remove a specific catalog version from the DB catalog.",
    show_default=False,
)
@click.option(
    "-y",
    "--skip_confirm",
    default=False,
    is_flag=True,
    help="Flag to delete catalogs without confirm prompting.",
    show_default=False,
)
@click.option(
    "--kind",
    default="all",
    type=click.Choice(["tool", "prompt", "all"], case_sensitive=True),
    help="Kind of catalog to remove versions from.",
    show_default=True,
)
@click.pass_context
def clean(ctx, catalog, type_metadata, bucket, catalog_id, skip_confirm, kind):
    """Delete all or specific (catalog and/or activity) agent related files / collections."""
    ctx_obj: Context = ctx.obj
    clean_db = "db" in catalog
    clean_local = "local" in catalog

    # If a user specifies non-interactive AND does not specify skip_prompt, we will exit here.
    if not ctx_obj.interactive and not skip_confirm:
        click.secho(
            "WARNING: No action taken. Specify -y to delete catalogs without confirmation, "
            "or specify your command with interactive mode.",
            fg="yellow",
        )
        return

    # Similar to the rm command, we will prompt the user for each catalog to delete.
    if clean_local:
        if not skip_confirm:
            click.confirm(
                "Are you sure you want to delete catalogs and/or audit logs from your filesystem?", abort=True
            )
        cmd_clean(
            ctx=ctx_obj,
            is_local=clean_local,
            is_db=clean_db,
            bucket=None,
            cluster=None,
            catalog_ids=None,
            kind=None,
            type_metadata=type_metadata,
        )

    if clean_db:
        if not skip_confirm:
            click.confirm("Are you sure you want to delete catalogs and/or audit logs from the database?", abort=True)

        # Load all Couchbase connection related data from env
        connection_details_env = CouchbaseConnect(
            connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
            username=os.getenv("AGENT_CATALOG_USERNAME"),
            password=os.getenv("AGENT_CATALOG_PASSWORD"),
            host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
            certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
        )

        # Establish a connection
        err, cluster = get_connection(conn=connection_details_env)
        if err:
            raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        # Determine the bucket.
        buckets = get_buckets(cluster=cluster)
        if bucket is None and ctx_obj.interactive:
            bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

        elif bucket is not None and bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\nRun agentc --help for more information."
            )

        elif bucket is None and not ctx_obj.interactive:
            raise ValueError(
                "Bucket must be specified to delete catalog from the database."
                "Add --bucket BUCKET_NAME to your command or run 'agent clean' in interactive mode."
            )

        # Perform our clean operation.
        kind_list = ["tool", "prompt"] if kind == "all" else [kind]
        cmd_clean(
            ctx=ctx.obj,
            is_db=clean_db,
            is_local=clean_local,
            bucket=bucket,
            cluster=cluster,
            catalog_ids=catalog_id,
            kind=kind_list,
        )
        cluster.close()

    if not clean_db and not clean_local:
        raise ValueError(
            "No catalogs specified to clean. "
            "Please specify either 'local' or 'db' or both to clean your catalog(s). "
        )


@click_main.command()
@click.pass_context
def env(ctx):
    """Return all agentc related environment and configuration parameters as a JSON object."""
    cmd_env(ctx=ctx.obj)


@click_main.command()
@click.argument(
    "kind",
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
    default="tool",
)
@click.option(
    "--query",
    default=None,
    help="User query describing the task for which tools / prompts are needed. "
    "This field or --name must be specified.",
    show_default=False,
)
@click.option(
    "--name",
    default=None,
    help="Name of catalog item to retrieve from the catalog directly. " "This field or --query must be specified.",
    show_default=False,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to search.",
    show_default=False,
)
@click.option(
    "--limit",
    default=1,
    help="Maximum number of results to show.",
    show_default=True,
)
@click.option(
    "--include-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click.option(
    "--refiner",
    type=click.Choice(["ClosestCluster", "None"], case_sensitive=False),
    default=None,
    help="Class to post-process (rerank, prune, etc...) find results.",
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
    "-cid",
    "--catalog-id",
    type=str,
    default=LATEST_SNAPSHOT_VERSION,
    help="Catalog ID that uniquely specifies a catalog version / snapshot (git commit id).",
    show_default=True,
)
@click.option(
    "-db",
    "--search-db",
    default=False,
    is_flag=True,
    help="Flag to force a DB-only search.",
    show_default=True,
)
@click.option(
    "-local",
    "--search-local",
    default=False,
    is_flag=True,
    help="Flag to force a local-only search.",
    show_default=True,
)
@click.pass_context
def find(
    ctx, query, name, kind, bucket, limit, include_dirty, refiner, annotations, catalog_id, search_db, search_local
):
    """Find items from the catalog based on a natural language QUERY string or by name."""
    ctx_obj: Context = ctx.obj

    # Perform a best-effort attempt to connect to the database if search_db is not raised.
    if not search_local:
        try:
            # Load all Couchbase connection related data from env
            connection_details_env = CouchbaseConnect(
                connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
                username=os.getenv("AGENT_CATALOG_USERNAME"),
                password=os.getenv("AGENT_CATALOG_PASSWORD"),
                host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
                certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
            )

            # Establish a connection
            err, cluster = get_connection(conn=connection_details_env)
            if err and search_db:
                raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        except pydantic.ValidationError as e:
            cluster = None
            if search_db:
                raise e
    else:
        cluster = None

    if cluster is not None:
        # Determine the bucket.
        buckets = get_buckets(cluster=cluster)
        if bucket is None and ctx_obj.interactive:
            bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

        elif bucket is not None and bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\nRun agentc --help for more information."
            )

        elif bucket is None and not ctx_obj.interactive:
            raise ValueError(
                "Bucket must be specified to search the database catalog."
                "Add --bucket BUCKET_NAME to your command or run agentc clean in interactive mode."
            )

    else:
        bucket = None

    cmd_find(
        ctx=ctx.obj,
        query=query,
        name=name,
        kind=kind,
        limit=limit,
        include_dirty=include_dirty,
        refiner=refiner,
        annotations=annotations,
        catalog_id=catalog_id,
        bucket=bucket,
        cluster=cluster,
        force_db=search_db,
    )
    if cluster is not None:
        cluster.close()


@click_main.command()
@click.argument("source_dirs", nargs=-1)
@click.option(
    "--prompts/--no-prompts",
    is_flag=True,
    default=True,
    help="Flag to (avoid) ignoring prompts when indexing source files into the local catalog.",
    show_default=True,
)
@click.option(
    "--tools/--no-tools",
    is_flag=True,
    default=True,
    help="Flag to (avoid) ignoring tools when indexing source files into the local catalog.",
    show_default=True,
)
@click.option(
    "-em",
    "--embedding-model",
    default=DEFAULT_EMBEDDING_MODEL,
    help="Embedding model used when indexing source files into the local catalog.",
    show_default=True,
)
@click.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help="Flag to prevent catalog changes.",
    show_default=True,
)
@click.pass_context
def index(ctx, source_dirs, tools, prompts, embedding_model, dry_run):
    """Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""

    if not source_dirs:
        raise ValueError(
            "Source directories to index not provided!!\n"
            "Please use the command 'agentc index --help' for more information."
        )

    kinds = list()
    if tools:
        kinds.append("tool")
    if prompts:
        kinds.append("prompt")
    if len(kinds) == 0:
        raise ValueError(
            "No kinds specified!\n"
            "Please specify at least one of 'tool' (via --tools) or 'prompt' (via --prompts) to index the "
            "source directories."
        )
    cmd_index(
        ctx=ctx.obj,
        source_dirs=source_dirs,
        kinds=kinds,
        embedding_model_name=embedding_model,
        dry_run=dry_run,
    )


@click_main.command()
@click.argument(
    "kind",
    nargs=-1,
    type=click.Choice(["tool", "prompt", "log"], case_sensitive=False),
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to publish to.",
    show_default=False,
)
@click.option(
    "-an",
    "--annotations",
    multiple=True,
    type=click.Tuple([str, str]),
    default=[],
    help="Snapshot level annotations to be added while publishing catalogs.",
    show_default=True,
)
@click.pass_context
def publish(ctx, kind, bucket, annotations):
    """Upload the local catalog and/or logs to a Couchbase instance.
    By default, only tools and prompts are published unless log is specified."""
    ctx_obj: Context = ctx.obj

    # By default, we'll publish everything.
    kind = ["tool", "prompt"] if len(kind) == 0 else list(kind)

    # Load all Couchbase connection related data from env
    connection_details_env = CouchbaseConnect(
        connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
        username=os.getenv("AGENT_CATALOG_USERNAME"),
        password=os.getenv("AGENT_CATALOG_PASSWORD"),
        host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
        certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
    )

    # Establish a connection
    err, cluster = get_connection(conn=connection_details_env)
    if err:
        raise ValueError(f"Unable to connect to Couchbase!\n{err}")

    # Determine the bucket.
    buckets = get_buckets(cluster=cluster)
    cluster.close()
    if bucket is None and ctx_obj.interactive:
        bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

    elif bucket is not None and bucket not in buckets:
        raise ValueError(
            "Bucket does not exist!\n"
            f"Available buckets from cluster are: {','.join(buckets)}\n"
            f"Run agentc publish --help for more information."
        )

    elif bucket is None and not ctx_obj.interactive:
        raise ValueError(
            "Bucket must be specified to publish to the database catalog."
            "Add --bucket BUCKET_NAME to your command or run agentc clean in interactive mode."
        )

    # Get keyspace and connection details
    keyspace_details = Keyspace(bucket=bucket, scope=DEFAULT_CATALOG_SCOPE)

    cmd_publish(
        ctx=ctx.obj,
        kind=kind,
        annotations=annotations,
        keyspace=keyspace_details,
        connection_details_env=connection_details_env,
    )


# TODO (GLENN): We should make kind an argument here (similar to publish and clean).
@click_main.command()
@click.argument(
    "kind",
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
    nargs=-1,
)
@click.option(
    "--include-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and compare against dirty source files.",
    show_default=True,
)
@click.option(
    "-db",
    "--status-db",
    default=False,
    is_flag=True,
    help="Flag to check status of catalogs in the Cluster.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of Couchbase bucket that is being used for agentc functionalities.",
    show_default=True,
)
@click.option(
    "--compare",
    default=None,
    is_flag=True,
    help="Flag to compare the local catalog with the last published catalog.",
    show_default=True,
)
@click.pass_context
def status(ctx, kind, include_dirty, status_db, bucket, compare):
    """Show the status of the local catalog."""
    ctx_obj: Context = ctx.obj

    if len(kind) == 0:
        kind = ["tool", "prompt"]

    if status_db or compare:
        # Get keyspace and connection details
        keyspace_details = Keyspace(bucket="", scope=DEFAULT_CATALOG_SCOPE)

        # Load all Couchbase connection related data from env
        connection_details_env = CouchbaseConnect(
            connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
            username=os.getenv("AGENT_CATALOG_USERNAME"),
            password=os.getenv("AGENT_CATALOG_PASSWORD"),
            host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
            certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
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
            bucket = click.prompt("Please select a bucket: ", type=click.Choice(buckets), show_choices=True)
        elif bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\n"
                f"Run agentc status --help for more information."
            )
        keyspace_details.bucket = bucket

        cmd_status(
            ctx_obj,
            kind=kind,
            include_dirty=include_dirty,
            status_db=status_db,
            bucket=keyspace_details.bucket,
            cluster=cluster,
            compare=compare,
        )
    else:
        cmd_status(ctx.obj, kind=kind, include_dirty=include_dirty, status_db=status_db)


@click_main.command()
@click.pass_context
def version(ctx):
    """Show the current version of agentc."""
    cmd_version(ctx.obj)


@click_main.command()
@click.option(
    "--query",
    default=None,
    help="User query describing the task for which tools / prompts are needed. "
    "This field or --name must be specified.",
    show_default=False,
)
@click.option(
    "--name",
    default=None,
    help="Name of catalog item to retrieve from the catalog directly. " "This field or --query must be specified.",
    show_default=False,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to search.",
    show_default=False,
)
@click.option(
    "--include-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click.option(
    "--refiner",
    type=click.Choice(["ClosestCluster", "None"], case_sensitive=False),
    default=None,
    help="Class to post-process (rerank, prune, etc...) find results.",
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
    "-cid",
    "--catalog-id",
    type=str,
    default=LATEST_SNAPSHOT_VERSION,
    help="Catalog ID that uniquely specifies a catalog version / snapshot (git commit id).",
    show_default=True,
)
@click.option(
    "-db",
    "--search-db",
    default=False,
    is_flag=True,
    help="Flag to force a DB-only search.",
    show_default=True,
)
@click.option(
    "-local",
    "--search-local",
    default=False,
    is_flag=True,
    help="Flag to force a local-only search.",
    show_default=True,
)
@click.pass_context
def execute(ctx, query, name, bucket, include_dirty, refiner, annotations, catalog_id, search_db, search_local):
    """Search and execute a specific tool."""
    ctx_obj: Context = ctx.obj

    # Perform a best-effort attempt to connect to the database if search_db is not raised.
    if not search_local:
        try:
            # Load all Couchbase connection related data from env
            connection_details_env = CouchbaseConnect(
                connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
                username=os.getenv("AGENT_CATALOG_USERNAME"),
                password=os.getenv("AGENT_CATALOG_PASSWORD"),
                host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
                certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
            )

            # Establish a connection
            err, cluster = get_connection(conn=connection_details_env)
            if err and search_db:
                raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        except pydantic.ValidationError as e:
            cluster = None
            if search_db:
                raise e
    else:
        cluster = None

    if cluster is not None:
        # Determine the bucket.
        buckets = get_buckets(cluster=cluster)
        if bucket is None and ctx_obj.interactive:
            bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

        elif bucket is not None and bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\nRun agentc --help for more information."
            )

        elif bucket is None and not ctx_obj.interactive:
            raise ValueError(
                "Bucket must be specified to search the database catalog."
                "Add --bucket BUCKET_NAME to your command or run agentc clean in interactive mode."
            )

    else:
        bucket = None

    cmd_execute(
        ctx=ctx.obj,
        query=query,
        name=name,
        include_dirty=include_dirty,
        refiner=refiner,
        annotations=annotations,
        catalog_id=catalog_id,
        bucket=bucket,
        cluster=cluster,
        force_db=search_db,
    )


@click_main.command()
@click.argument(
    "kind",
    nargs=-1,
    type=click.Choice(["tool", "prompt"], case_sensitive=False),
)
@click.option(
    "-db",
    "--search-db",
    default=False,
    is_flag=True,
    help="Flag to force a DB-only search.",
    show_default=True,
)
@click.option(
    "-local",
    "--search-local",
    default=False,
    is_flag=True,
    help="Flag to force a local-only search.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of Couchbase bucket that is being used for agentc functionalities.",
    show_default=True,
)
@click.pass_context
def ls(ctx, kind, search_db, search_local, bucket):
    """List all indexed tools and/or prompts in the catalog."""
    ctx_obj: Context = ctx.obj

    if search_db and search_local:
        raise ValueError(
            "Both local and database force search tags should not be used simultaneously. Please specify one or don't specify any tag to search both."
        )

    # By default, we'll list everything.
    if len(kind) == 0:
        kind = ["tool", "prompt"]

    # Perform a best-effort attempt to connect to the database if search_db is not raised.
    if not search_local:
        try:
            # Load all Couchbase connection related data from env
            connection_details_env = CouchbaseConnect(
                connection_url=os.getenv("AGENT_CATALOG_CONN_STRING"),
                username=os.getenv("AGENT_CATALOG_USERNAME"),
                password=os.getenv("AGENT_CATALOG_PASSWORD"),
                host=get_host_name(os.getenv("AGENT_CATALOG_CONN_STRING")),
                certificate=os.getenv("AGENT_CATALOG_CONN_ROOT_CERTIFICATE"),
            )

            # Establish a connection
            err, cluster = get_connection(conn=connection_details_env)
            if err and search_db:
                raise ValueError(f"Unable to connect to Couchbase!\n{err}")

        except pydantic.ValidationError as e:
            cluster = None
            if search_db:
                raise e
    else:
        cluster = None

    if cluster is not None:
        # Determine the bucket.
        buckets = get_buckets(cluster=cluster)
        if bucket is None and ctx_obj.interactive:
            bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

        elif bucket is not None and bucket not in buckets:
            raise ValueError(
                "Bucket does not exist!\n"
                f"Available buckets from cluster are: {','.join(buckets)}\nRun agentc --help for more information."
            )

        elif bucket is None and not ctx_obj.interactive:
            raise ValueError(
                "Bucket must be specified to search the database catalog."
                "Add --bucket BUCKET_NAME to your command or run the command in interactive mode."
            )

    else:
        bucket = None

    cmd_ls(ctx=ctx_obj, kind_list=kind, bucket=bucket, cluster=cluster, force_db=search_db)


# @click_main.command()
# @click.option(
#     "--host-port",
#     default=DEFAULT_WEB_HOST_PORT,
#     envvar="AGENT_CATALOG_WEB_HOST_PORT",
#     help="The host:port to listen on.",
#     show_default=True,
# )
# @click.option(
#     "--debug/--no-debug",
#     envvar="AGENT_CATALOG_WEB_DEBUG",
#     default=True,
#     help="Debug mode.",
#     show_default=True,
# )
# @click.pass_context
# def web(ctx, host_port, debug):
#     """Start a local web server to view our tools."""
#     cmd_web(ctx.obj, host_port, debug)


def main():
    try:
        click_main()
    except Exception as e:
        if isinstance(e, ValidationError):
            for err in e.errors():
                err_it = iter(err["msg"].splitlines())
                click.secho(f"ERROR: {next(err_it)}", fg="red", err=True)
                try:
                    while True:
                        click.secho(textwrap.indent(next(err_it), "       "), fg="red", err=True)

                except StopIteration:
                    pass

        else:
            err_it = iter(str(e).splitlines())
            click.secho(f"ERROR: {next(err_it)}", fg="red", err=True)
            try:
                while True:
                    click.secho(textwrap.indent(next(err_it), "       "), fg="red", err=True)

            except StopIteration:
                pass

        if os.getenv("AGENT_CATALOG_DEBUG") is not None:
            # Set AGENT_CATALOG_DEBUG so standard python stack trace is emitted.
            raise e

        sys.exit(1)


if __name__ == "__main__":
    main()
