import click_extra
import cloup
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
# From: https://click_extra.palletsprojects.com/en/8.1.x/advanced/#command-aliases
class AliasedGroup(click_extra.ExtraGroup):
    def get_command(self, ctx, cmd_name):
        rv = click_extra.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv

        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None

        if len(matches) == 1:
            return click_extra.Group.get_command(self, ctx, matches[0])

        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx, args):
        # Always return the full command name.
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args


@click_extra.group(
    cls=AliasedGroup,
    epilog="See https://couchbaselabs.github.io/agent-catalog/index.html for more information.",
    context_settings={
        "formatter_settings": click_extra.HelpExtraFormatter.settings(
            theme=click_extra.HelpExtraTheme.dark().with_(
                # "click_extra" at the moment only supports dark themes -- but unfortunately this does not play well
                # with light backgrounds (e.g., our docs).
                # TODO (GLENN): When click_extra gets around to making an actual light theme, use that instead.
                invoked_command=cloup.Style(fg=cloup.Color.cyan, italic=True)
            )
        )
    },
)
@click_extra.option(
    "-v",
    "--verbose",
    default=DEFAULT_VERBOSITY_LEVEL,
    type=click_extra.IntRange(min=0, max=2, clamp=True),
    count=True,
    help="Flag to enable verbose output.",
    show_default=True,
)
@click_extra.option(
    "-i/-ni",
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Flag to enable interactive mode.",
    show_default=True,
)
@click_extra.pass_context
def agentc(ctx: click_extra.Context, verbose: int, interactive: bool):
    """
    The Couchbase Agent Catalog command line tool.
    """
    ctx.obj = Config(
        # TODO (GLENN): We really need to use this "verbosity_level" parameter more.
        verbosity_level=verbose,
        with_interaction=interactive,
    )


@agentc.command()
@click_extra.argument("targets", type=click_extra.Choice(["catalog", "activity"], case_sensitive=False), nargs=-1)
@click_extra.option(
    "--db/--no-db",
    default=True,
    is_flag=True,
    help="Flag to enable / disable DB initialization.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to enable / disable local FS initialization.",
    show_default=True,
)
@click_extra.option(
    "--add-hook-for",
    multiple=True,
    default=None,
    type=str,
    help="Source directory to add a post-commit hook for.",
    show_default=False,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to initialize in.",
    show_default=False,
)
@click_extra.pass_context
def init(
    ctx: click_extra.Context,
    targets: list[typing.Literal["catalog", "activity"]],
    db: bool,
    local: bool,
    add_hook_for: list[str] = None,
    bucket: str = None,
):
    """
    Initialize the necessary files/collections for your working Agent Catalog environment.
    """
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
        add_hook_for=add_hook_for,
    )


@agentc.command()
@click_extra.option(
    "-o",
    "--output",
    default=os.getcwd(),
    show_default=False,
    type=click_extra.Path(exists=False, file_okay=False, dir_okay=True, path_type=pathlib.Path),
    help="Location to save the generated tool / prompt to. Defaults to your current working directory.",
)
@click_extra.option(
    "--kind", type=click_extra.Choice([c for c in RecordKind], case_sensitive=False), default=None, show_default=True
)
@click_extra.pass_context
def add(ctx, output: pathlib.Path, kind: RecordKind):
    """
    Interactively create a new tool or prompt and save it to the filesystem (output).
    You MUST edit the generated file as per your requirements!
    """
    cfg: Config = ctx.obj
    if not cfg.with_interaction:
        click_extra.secho(
            "ERROR: Cannot run agentc add in non-interactive mode! "
            "Specify your command without the non-interactive flag. ",
            fg="red",
        )
        return

    if kind is None:
        kind = click_extra.prompt("Record Kind", type=click_extra.Choice([c for c in RecordKind], case_sensitive=False))
    cmd_add(cfg=cfg, output=output, kind=kind)


@agentc.command()
@click_extra.argument(
    "targets",
    type=click_extra.Choice(["catalog", "activity"], case_sensitive=False),
    nargs=-1,
)
@click_extra.option(
    "--db/--no-db",
    default=True,
    is_flag=True,
    help="Flag to perform / not-perform a DB clean.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to perform / not-perform a local FS clean.",
    show_default=True,
)
@click_extra.option(
    "--tools/--no-tools",
    default=True,
    is_flag=True,
    help="Flag to clean / avoid-cleaning the tool-catalog.",
    show_default=True,
)
@click_extra.option(
    "--prompts/--no-prompts",
    default=True,
    is_flag=True,
    help="Flag to clean / avoid-cleaning the prompt-catalog.",
    show_default=True,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to remove Agent Catalog from.",
    show_default=False,
)
@click_extra.option(
    "-cid",
    "--catalog-id",
    multiple=True,
    default=None,
    type=str,
    help="Catalog ID used to remove a specific catalog version from the DB catalog.",
    show_default=False,
)
@click_extra.option(
    "-y",
    "--yes",
    default=False,
    is_flag=True,
    help="Flag to delete local-FS and DB catalog data without confirmation.",
    show_default=False,
)
@click_extra.option(
    "-d",
    "--date",
    default=None,
    type=str,
    help="Datetime of the oldest log entry to keep (older log entries will be deleted).",
    show_default=False,
)
@click_extra.pass_context
def clean(
    ctx: click_extra.Context,
    targets: list[typing.Literal["catalog", "activity"]],
    db: bool,
    local: bool,
    tools: bool,
    prompts: bool,
    catalog_id: list[str] = None,
    bucket: str = None,
    yes: bool = False,
    date: str = None,
):
    """Delete all or specific (catalog and/or activity) Agent Catalog related files / collections."""
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
        click_extra.secho(
            'WARNING: No action taken. "catalog" with the flags --no-tools and --no-prompts have ' "been specified.",
            fg="yellow",
        )
        return

    # If a user specifies date and does not specify a sole target of "activity", then we will error out.
    if date is not None and len(targets) != 1 and targets[0] != "activity":
        click_extra.secho(
            "ERROR: When using the date option, only activity logs can be deleted (not catalog entries). "
            "For example: `agentc clean activity --date/-d '2021-09-01T00:00:00'.",
            fg="red",
        )
        return

    # If a user specifies non-interactive AND does not specify yes, we will exit here.
    if not cfg.with_interaction and not yes:
        click_extra.secho(
            "WARNING: No action taken. Specify -y to delete catalogs without confirmation, "
            "or specify your command with interactive mode.",
            fg="yellow",
        )
        return

    # Similar to the rm command, we will prompt the user for each catalog to delete.
    if local:
        if not yes:
            click_extra.confirm(
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
            click_extra.confirm(
                "Are you sure you want to delete catalogs and/or audit logs from the database?", abort=True
            )

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


@agentc.command()
@click_extra.pass_context
def env(ctx):
    """Return all Agent Catalog related environment and configuration parameters as a JSON object."""
    cmd_env(cfg=ctx.obj)


@agentc.command()
@click_extra.argument(
    "kind",
    type=click_extra.Choice(["tools", "prompts"], case_sensitive=False),
)
@click_extra.option(
    "--query",
    default=None,
    help="User query describing the task for which tools / prompts are needed. "
    "This field or --name must be specified.",
    show_default=False,
)
@click_extra.option(
    "--name",
    default=None,
    help="Name of catalog item to retrieve from the catalog directly. This field or --query must be specified.",
    show_default=False,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to search.",
    show_default=False,
)
@click_extra.option(
    "--limit",
    default=1,
    type=int,
    help="Maximum number of results to show.",
    show_default=True,
)
@click_extra.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click_extra.option(
    "--refiner",
    type=click_extra.Choice(["ClosestCluster", "None"], case_sensitive=False),
    default=None,
    help="Class to post-process (rerank, prune, etc...) find results.",
    show_default=True,
)
@click_extra.option(
    "-an",
    "--annotations",
    type=str,
    default=None,
    help='Tool-specific annotations to filter by, specified using KEY="VALUE" (AND|OR KEY="VALUE")*.',
    show_default=True,
)
@click_extra.option(
    "-cid",
    "--catalog-id",
    type=str,
    default=LATEST_SNAPSHOT_VERSION,
    help="Catalog ID that uniquely specifies a catalog version / snapshot (git commit id).",
    show_default=True,
)
@click_extra.option(
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while searching.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while searching.",
    show_default=True,
)
@click_extra.pass_context
def find(
    ctx: click_extra.Context,
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
    """Find items from the catalog based on a natural language string (query) or by name."""
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


@agentc.command()
@click_extra.argument("sources", nargs=-1)
@click_extra.option(
    "--prompts/--no-prompts",
    is_flag=True,
    default=True,
    help="Flag to look for / ignore prompts when indexing source files into the local catalog.",
    show_default=True,
)
@click_extra.option(
    "--tools/--no-tools",
    is_flag=True,
    default=True,
    help="Flag to look for / ignore tools when indexing source files into the local catalog.",
    show_default=True,
)
@click_extra.option(
    "--dry-run",
    default=False,
    is_flag=True,
    help="Flag to prevent catalog changes.",
    show_default=True,
)
@click_extra.pass_context
def index(ctx: click_extra.Context, sources: list[str], tools: bool, prompts: bool, dry_run: bool = False):
    """Walk the source directory trees (sources) to index source files into the local catalog.
    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""
    kind = list()
    if tools:
        kind.append("tool")
    if prompts:
        kind.append("prompt")

    if not sources:
        click_extra.secho(
            "WARNING: No action taken. No source directories have been specified. "
            "Please use the command 'agentc index --help' for more information.",
            fg="yellow",
        )
        return

    # Both "--no-tools" and "--no-prompts" have been specified.
    if len(kind) == 0:
        click_extra.secho(
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


@agentc.command()
@click_extra.argument(
    "kind",
    nargs=-1,
    type=click_extra.Choice(["tools", "prompts", "logs"], case_sensitive=False),
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to publish to.",
    show_default=False,
)
@click_extra.option(
    "-an",
    "--annotations",
    multiple=True,
    type=click_extra.Tuple([str, str]),
    default=[],
    help="Snapshot level annotations to be added while publishing catalogs.",
    show_default=True,
)
@click_extra.pass_context
def publish(
    ctx: click_extra.Context, kind: list[typing.Literal["tools", "prompts", "logs"]], bucket: str, annotations: str
):
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


@agentc.command()
@click_extra.argument(
    "kind",
    type=click_extra.Choice(["tools", "prompts"], case_sensitive=False),
    nargs=-1,
)
@click_extra.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and compare against dirty source files.",
    show_default=True,
)
@click_extra.option(
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while displaying status.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while displaying status.",
    show_default=True,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket hosting the Agent Catalog.",
    show_default=False,
)
@click_extra.pass_context
def status(
    ctx: click_extra.Context,
    kind: list[typing.Literal["tools", "prompts"]],
    dirty: bool,
    db: bool = None,
    local: bool = True,
    bucket: str = None,
):
    """Show the (aggregate) status of your Agent Catalog environment."""
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


@agentc.command()
@click_extra.pass_context
def version(ctx):
    """Show the current version of Agent Catalog."""
    cmd_version(ctx.obj)


@agentc.command()
@click_extra.option(
    "--query",
    default=None,
    help="User query describing the task for which tools / prompts are needed. "
    "This field or --name must be specified.",
    show_default=False,
)
@click_extra.option(
    "--name",
    default=None,
    help="Name of catalog item to retrieve from the catalog directly. This field or --query must be specified.",
    show_default=False,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of the Couchbase bucket to search.",
    show_default=False,
)
@click_extra.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click_extra.option(
    "--refiner",
    type=click_extra.Choice(["ClosestCluster", "None"], case_sensitive=False),
    default=None,
    help="Class to post-process (rerank, prune, etc...) find results.",
    show_default=True,
)
@click_extra.option(
    "-an",
    "--annotations",
    type=str,
    default=None,
    help='Tool-specific annotations to filter by, specified using KEY="VALUE" (AND|OR KEY="VALUE")*.',
    show_default=True,
)
@click_extra.option(
    "-cid",
    "--catalog-id",
    type=str,
    default=LATEST_SNAPSHOT_VERSION,
    help="Catalog ID that uniquely specifies a catalog version / snapshot (git commit id).",
    show_default=True,
)
@click_extra.option(
    "--db/--no-db",
    default=None,
    is_flag=True,
    help="Flag to include / exclude items from the DB-catalog while searching.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to include / exclude items from the local-FS-catalog while searching.",
    show_default=True,
)
@click_extra.pass_context
def execute(
    ctx: click_extra.Context,
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
    """Search for and subsequently execute a specific tool."""
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


@agentc.command()
@click_extra.argument(
    "kind",
    nargs=-1,
    type=click_extra.Choice(["tools", "prompts"], case_sensitive=False),
)
@click_extra.option(
    "--db/--no-db",
    default=False,
    is_flag=True,
    help="Flag to force a DB-only search.",
    show_default=True,
)
@click_extra.option(
    "--local/--no-local",
    default=True,
    is_flag=True,
    help="Flag to force a local-only search.",
    show_default=True,
)
@click_extra.option(
    "--dirty/--no-dirty",
    default=True,
    is_flag=True,
    help="Flag to process and search amongst dirty source files.",
    show_default=True,
)
@click_extra.option(
    "--bucket",
    default=None,
    type=str,
    help="Name of Couchbase bucket that is being used for Agent Catalog.",
    show_default=True,
)
@click_extra.pass_context
def ls(
    ctx: click_extra.Context,
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

    if db:
        # In contrast to the other commands, we do not perform a best effort attempt to connect to Couchbase here.
        validate_or_prompt_for_bucket(cfg, bucket)

    cmd_ls(cfg=cfg, kind=kind, include_dirty=dirty, with_local=local, with_db=db)


# @click_main.command()
# @click_extra.option(
#     "--host-port",
#     default=DEFAULT_WEB_HOST_PORT,
#     envvar="AGENT_CATALOG_WEB_HOST_PORT",
#     help="The host:port to listen on.",
#     show_default=True,
# )
# @click_extra.option(
#     "--debug/--no-debug",
#     envvar="AGENT_CATALOG_WEB_DEBUG",
#     default=True,
#     help="Debug mode.",
#     show_default=True,
# )
# @click_extra.pass_context
# def web(ctx, host_port, debug):
#     """Start a local web server to view our tools."""
#     cmd_web(ctx.obj, host_port, debug)


def main():
    try:
        agentc()
    except Exception as e:
        if isinstance(e, pydantic.ValidationError):
            for err in e.errors():
                err_it = iter(err["msg"].splitlines())
                click_extra.secho(f"ERROR: {next(err_it)}", fg="red", err=True)
                try:
                    while True:
                        click_extra.secho(textwrap.indent(next(err_it), "       "), fg="red", err=True)

                except StopIteration:
                    pass

        else:
            err_it = iter(str(e).splitlines())
            click_extra.secho(f"ERROR: {next(err_it)}", fg="red", err=True)
            try:
                while True:
                    click_extra.secho(textwrap.indent(next(err_it), "       "), fg="red", err=True)

            except StopIteration:
                pass

        if os.getenv("AGENT_CATALOG_DEBUG") is not None:
            # Set AGENT_CATALOG_DEBUG so standard python stack trace is emitted.
            raise e

        sys.exit(1)


if __name__ == "__main__":
    main()
