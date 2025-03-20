import click
import couchbase.cluster
import couchbase.exceptions
import logging
import os
import pathlib
import pydantic
import sys
import textwrap
import typing

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
from .util import validate_or_prompt_for_bucket
from agentc_core.config import LATEST_SNAPSHOT_VERSION
from agentc_core.config.config import Config
from agentc_core.defaults import DEFAULT_VERBOSITY_LEVEL
from agentc_core.record.descriptor import RecordKind

# Keeping this here, the logging these libraries do can be pretty verbose.
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("openapi_parser").setLevel(logging.ERROR)


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
    epilog="See: https://docs.couchbase.com or https://couchbaselabs.github.io/agent-catalog/index.html# for more "
    "information.",
    context_settings=dict(max_content_width=800),
)
@click.option(
    "-v",
    "--verbose",
    default=DEFAULT_VERBOSITY_LEVEL,
    type=click.IntRange(min=0, max=2, clamp=True),
    count=True,
    help="Flag to enable verbose output.",
    show_default=True,
)
@click.option(
    "-i/-ni",
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Flag to enable interactive mode.",
    show_default=True,
)
@click.pass_context
def click_main(ctx: click.Context, verbose: int, interactive: bool):
    """The Couchbase Agent Catalog command line tool."""
    ctx.obj = Config(
        # TODO (GLENN): We really need to use this "verbosity_level" parameter more.
        verbosity_level=verbose,
        with_interaction=interactive,
    )


@click_main.command()
@click.argument("targets", type=click.Choice(["catalog", "activity"], case_sensitive=False), nargs=-1)
@click.option(
    "--db/--no-db",
    default=True,
    is_flag=True,
    help="Flag to enable / disable DB initialization.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to enable / disable local FS initialization.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to initialize in.",
    show_default=False,
)
@click.pass_context
def init(
    ctx: click.Context, targets: list[typing.Literal["catalog", "activity"]], db: bool, local: bool, bucket: str = None
):
    """Initialize the necessary files/collections for local/database catalog."""
    cfg: Config = ctx.obj

    # By default, we will initialize everything.
    if not targets:
        targets = ["catalog", "activity"]

    # Set our bucket (if it is not already set).
    if db:
        validate_or_prompt_for_bucket(cfg, bucket)

    cmd_init(
        cfg=cfg,
        targets=targets,
        db=db,
        local=local,
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
    "--kind", type=click.Choice([c for c in RecordKind], case_sensitive=False), default=None, show_default=True
)
@click.pass_context
def add(ctx, output: pathlib.Path, kind: RecordKind):
    """Interactively create a new tool or prompt and save it to the filesystem (output).
    You MUST edit the generated file as per your requirements!"""
    cfg: Config = ctx.obj
    if not cfg.with_interaction:
        click.secho(
            "ERROR: Cannot run agentc add in non-interactive mode! "
            "Specify your command without the non-interactive flag. ",
            fg="red",
        )
        return

    if kind is None:
        kind = click.prompt("Record Kind", type=click.Choice([c for c in RecordKind], case_sensitive=False))
    cmd_add(cfg=cfg, output=output, kind=kind)


@click_main.command()
@click.argument(
    "targets",
    type=click.Choice(["catalog", "activity"], case_sensitive=False),
    nargs=-1,
)
@click.option(
    "--db/--no-db",
    default=True,
    is_flag=True,
    help="Flag to perform / not-perform a DB clean.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to perform / not-perform a local FS clean.",
    show_default=True,
)
@click.option(
    "--tools/--no-tools",
    default=True,
    is_flag=True,
    help="Flag to clean / avoid-cleaning the tool-catalog.",
    show_default=True,
)
@click.option(
    "--prompts/--no-prompts",
    default=True,
    is_flag=True,
    help="Flag to clean / avoid-cleaning the prompt-catalog.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to remove Agent Catalog from.",
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
    "--yes",
    default=False,
    is_flag=True,
    help="Flag to delete local-FS and DB catalog data without confirmation.",
    show_default=False,
)
@click.pass_context
def clean(
    ctx: click.Context,
    targets: list[typing.Literal["catalog", "activity"]],
    db: bool,
    local: bool,
    tools: bool,
    prompts: bool,
    catalog_id: list[str] = None,
    bucket: str = None,
    yes: bool = False,
):
    """Delete all or specific (catalog and/or activity) agent related files / collections."""
    cfg: Config = ctx.obj

    # By default, we will clean everything.
    if not targets:
        targets = ["catalog", "activity"]

    kind: list[typing.Literal["tool", "prompt"]] = list()
    if tools:
        kind.append("tool")
    if prompts:
        kind.append("prompt")

    # If a user specifies both --no-tools and --no-prompts AND only "catalog", we have nothing to delete.
    if len(kind) == 0 and len(targets) == 1 and targets[0] == "catalog":
        click.secho(
            'WARNING: No action taken. "catalog" with the flags --no-tools and --no-prompts have ' "been specified.",
            fg="yellow",
        )
        return

    # If a user specifies non-interactive AND does not specify yes, we will exit here.
    if not cfg.with_interaction and not yes:
        click.secho(
            "WARNING: No action taken. Specify -y to delete catalogs without confirmation, "
            "or specify your command with interactive mode.",
            fg="yellow",
        )
        return

    # Similar to the rm command, we will prompt the user for each catalog to delete.
    if local:
        if not yes:
            click.confirm(
                "Are you sure you want to delete catalogs and/or audit logs from your filesystem?", abort=True
            )
        cmd_clean(
            cfg=cfg,
            targets=targets,
            kind=kind,
            is_local=True,
            is_db=False,
            catalog_ids=None,
        )

    if db:
        if not yes:
            click.confirm("Are you sure you want to delete catalogs and/or audit logs from the database?", abort=True)

        # Set our bucket (if it is not already set).
        validate_or_prompt_for_bucket(cfg, bucket)

        # Perform our clean operation.
        cmd_clean(
            cfg=cfg,
            is_local=False,
            is_db=True,
            catalog_ids=catalog_id,
            kind=kind,
            targets=targets,
        )


@click_main.command()
@click.pass_context
def env(ctx):
    """Return all agentc related environment and configuration parameters as a JSON object."""
    cmd_env(cfg=ctx.obj)


@click_main.command()
@click.argument(
    "kind",
    type=click.Choice(["tools", "prompts"], case_sensitive=False),
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
    help="Name of catalog item to retrieve from the catalog directly. This field or --query must be specified.",
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
    type=int,
    help="Maximum number of results to show.",
    show_default=True,
)
@click.option(
    "--dirty/--no-dirty",
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
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while searching.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while searching.",
    show_default=True,
)
@click.pass_context
def find(
    ctx: click.Context,
    kind: typing.Literal["tools", "prompts"],
    query: str = None,
    name: str = None,
    bucket: str = None,
    limit: int = 1,
    dirty: bool = True,
    refiner: typing.Literal["ClosestCluster", "None"] = "None",
    annotations: str = None,
    catalog_id: str = LATEST_SNAPSHOT_VERSION,
    db: bool | None = None,
    local: bool | None = True,
):
    """Find items from the catalog based on a natural language QUERY string or by name."""
    cfg: Config = ctx.obj

    # TODO (GLENN): We should perform the same best-effort work for search_local.
    # Perform a best-effort attempt to connect to the database if search_db is not raised.
    if db is None or db is True:
        try:
            validate_or_prompt_for_bucket(cfg, bucket)

        except (couchbase.exceptions.CouchbaseException, ValueError) as e:
            if db is True:
                raise e
            db = False

    cmd_find(
        cfg=cfg,
        kind=kind,
        with_db=db,
        with_local=local,
        query=query,
        name=name,
        limit=limit,
        include_dirty=dirty,
        refiner=refiner,
        annotations=annotations,
        catalog_id=catalog_id,
    )


@click_main.command()
@click.argument("sources", nargs=-1)
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
    "--dry-run",
    default=False,
    is_flag=True,
    help="Flag to prevent catalog changes.",
    show_default=True,
)
@click.pass_context
def index(ctx: click.Context, sources: list[str], tools: bool, prompts: bool, dry_run: bool = False):
    """Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""
    kind = list()
    if tools:
        kind.append("tool")
    if prompts:
        kind.append("prompt")

    if not sources:
        click.secho(
            "WARNING: No action taken. No source directories have been specified. "
            "Please use the command 'agentc index --help' for more information.",
            fg="yellow",
        )
        return

    # Both "--no-tools" and "--no-prompts" have been specified.
    if len(kind) == 0:
        click.secho(
            "WARNING: No action taken. Both flags --no-tools and --no-prompts have been specified.",
            fg="yellow",
        )
        return

    cmd_index(
        cfg=ctx.obj,
        source_dirs=sources,
        kinds=kind,
        dry_run=dry_run,
    )


@click_main.command()
@click.argument(
    "kind",
    nargs=-1,
    type=click.Choice(["tools", "prompts", "logs"], case_sensitive=False),
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
def publish(ctx: click.Context, kind: list[typing.Literal["tools", "prompts", "logs"]], bucket: str, annotations: str):
    """Upload the local catalog and/or logs to a Couchbase instance.
    By default, only tools and prompts are published unless log is explicitly specified."""
    kind = ["tools", "prompts"] if len(kind) == 0 else kind

    cfg: Config = ctx.obj
    validate_or_prompt_for_bucket(cfg, bucket)
    cmd_publish(
        cfg=cfg,
        kind=kind,
        annotations=annotations,
    )


@click_main.command()
@click.argument(
    "kind",
    type=click.Choice(["tools", "prompts"], case_sensitive=False),
    nargs=-1,
)
@click.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and compare against dirty source files.",
    show_default=True,
)
@click.option(
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while displaying status.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while displaying status.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket hosting the Agent Catalog.",
    show_default=False,
)
@click.pass_context
def status(
    ctx: click.Context,
    kind: list[typing.Literal["tools", "prompts"]],
    dirty: bool,
    db: bool = None,
    local: bool = True,
    bucket: str = None,
):
    """Show the status of the local-FS / remote-DB catalog."""
    cfg: Config = ctx.obj
    if len(kind) == 0:
        kind = ["tools", "prompts"]

    # TODO (GLENN): We should perform the same best-effort work for status_local.
    # Perform a best-effort attempt to connect to the database if status_db is not raised.
    if db is None or db is True:
        try:
            validate_or_prompt_for_bucket(cfg, bucket)

        except (couchbase.exceptions.CouchbaseException, ValueError) as e:
            if db is True:
                raise e
            db = False

    cmd_status(
        cfg=cfg,
        kind=kind,
        include_dirty=dirty,
        with_db=db,
        with_local=local,
    )


@click_main.command()
@click.pass_context
def version(ctx):
    """Show the current version of Agent Catalog."""
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
    help="Name of catalog item to retrieve from the catalog directly. This field or --query must be specified.",
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
    "--dirty/--no-dirty",
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
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while searching.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while searching.",
    show_default=True,
)
@click.pass_context
def execute(
    ctx: click.Context,
    query: str,
    name: str,
    dirty: bool = True,
    bucket: str = None,
    refiner: typing.Literal["ClosestCluster", "None"] = "None",
    annotations: str = None,
    catalog_id: list[str] = None,
    db: bool = None,
    local: bool = True,
):
    """Search and execute a specific tool."""
    cfg: Config = ctx.obj

    # TODO (GLENN): We should perform the same best-effort work for status_local.
    # Perform a best-effort attempt to connect to the database if status_db is not raised.
    if db is None or db is True:
        try:
            validate_or_prompt_for_bucket(cfg, bucket)

        except (couchbase.exceptions.CouchbaseException, ValueError) as e:
            if db is True:
                raise e
            db = False

    cmd_execute(
        cfg=cfg,
        with_db=db,
        with_local=local,
        query=query,
        name=name,
        include_dirty=dirty,
        refiner=refiner,
        annotations=annotations,
        catalog_id=catalog_id,
    )


@click_main.command()
@click.argument(
    "kind",
    nargs=-1,
    type=click.Choice(["tools", "prompts"], case_sensitive=False),
)
@click.option(
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to force a DB-only search.",
    show_default=True,
)
@click.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to force a local-only search.",
    show_default=True,
)
@click.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of Couchbase bucket that is being used for Agent Catalog.",
    show_default=True,
)
@click.pass_context
def ls(
    ctx: click.Context,
    kind: list[typing.Literal["tools", "prompts"]],
    db: bool = None,
    local: bool = True,
    dirty: bool = True,
    bucket: str = None,
):
    """List all indexed tools and/or prompts in the catalog."""
    cfg: Config = ctx.obj

    # By default, we'll list everything.
    if len(kind) == 0:
        kind = ["tools", "prompts"]

    # TODO (GLENN): We should perform the same best-effort work for status_local.
    # Perform a best-effort attempt to connect to the database if status_db is not raised.
    if db is None or db is True:
        try:
            validate_or_prompt_for_bucket(cfg, bucket)

        except (couchbase.exceptions.CouchbaseException, ValueError) as e:
            if db is True:
                raise e
            db = False

    cmd_ls(cfg=cfg, kind=kind, include_dirty=dirty, with_local=local, with_db=db)


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
        if isinstance(e, pydantic.ValidationError):
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
