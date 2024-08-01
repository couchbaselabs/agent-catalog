import json
import pathlib

import click
import dotenv

from .cmds import *


# TODO: Should we load from ".env.rosetta"?
# TODO: Or, perhaps even stage specific, like from ".env.rosetta.prod"?
dotenv.load_dotenv()


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


@click.group(cls=AliasedGroup,
             epilog='See: https://docs.couchbase.com for more information.')
@click.option('-c', '--catalog',
              default='.rosetta-catalog',
              type=click.Path(exists=False, file_okay=False, dir_okay=True),
              help='''Directory of local catalog files.
              The local catalog DIRECTORY should be checked into git.''',
              envvar='ROSETTA_CATALOG',
              show_default=True)
@click.option('-a', '--activity',
              default='.rosetta-activity',
              type=click.Path(exists=False, file_okay=False, dir_okay=True),
              help='''Directory of local activity files (runtime data).
              The local activity DIRECTORY should NOT be checked into git,
              as it holds runtime activity data like logs, call histories, etc.''',
              envvar='ROSETTA_ACTIVITY',
              show_default=True)
@click.option('-v', '--verbose',
              count=True,
              help='Enable verbose output.',
              envvar='ROSETTA_VERBOSE')
@click.pass_context
def main(ctx, catalog, activity, verbose):
    """A command line tool for Rosetta."""
    ctx.obj = ctx.obj or {
        'catalog': catalog,
        'activity': activity,
        'verbose': verbose
    }


@main.command()
@click.pass_context
def clean(ctx):
    """Clean up catalog, activity, generated files, etc."""
    cmd_clean(ctx.obj)


@main.command()
@click.pass_context
def env(ctx):
    """Show this program's env or configuration parameters as JSON."""
    cmd_env(ctx.obj)


@main.command()
@click.pass_context
def find(ctx):
    """Find tools, prompts, etc. from the catalog."""
    cmd_find(ctx.obj)


@main.command()
@click.argument('source_dirs', nargs=-1, required=True)
@click.option('-em', '--embedding-model',
              default=DEFAULT_EMBEDDING_MODEL,
              help='Embedding model when indexing source files into the local catalog.',
              show_default=True)
@click.pass_context
def index(ctx, source_dirs, embedding_model):
    """Walk source directory files for indexing into the local catalog.

    Source files that will be scanned include *.py, *.sqlpp, *.yaml, etc."""

    # TODO: The index command should default to the '.' directory / current directory.
    # TODO: The index command should ignore the '.git' subdirectory.
    # TODO: The index command should ignore whatever's in the '.gitignore' file.

    cmd_index(ctx.obj, source_dirs=source_dirs, embedding_model=embedding_model)


@main.command()
@click.pass_context
def publish(ctx):
    """Publish the local catalog to a database."""
    cmd_publish(ctx.obj)


@main.command()
@click.pass_context
def status(ctx):
    """Show the status of the local catalog."""
    cmd_status(ctx.obj)


@main.command()
@click.pass_context
def version(ctx):
    """Show the version of this tool."""
    cmd_version(ctx.obj)


@main.command()
@click.option('--host-port',
              default=DEFAULT_WEB_HOST_PORT,
              envvar='ROSETTA_WEB_HOST_PORT',
              help='The host:port to listen on.',
              show_default=True)
@click.option('--debug/--no-debug',
              envvar='ROSETTA_WEB_DEBUG',
              default=True,
              help='Debug mode.',
              show_default=True)
@click.pass_context
def web(ctx, host_port, debug):
    """Start local web server."""
    cmd_web(ctx.obj, host_port, debug)


if __name__ == '__main__':
    main()
