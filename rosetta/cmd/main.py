import json
import pathlib

import click
import dotenv

from .cmds import *


# TODO: Should we load from ".env.rosetta"?
# TODO: Or, perhaps even stage specific, like from ".env.rosetta.prod"?
dotenv.load_dotenv()


@click.group(epilog='See: https://docs.couchbase.com for more information.')
@click.option('-c', '--catalog',
              default='./catalog',
              type=click.Path(exists=False, file_okay=False, dir_okay=True),
              help='''Directory of local catalog files.
              The local catalog DIRECTORY should be checked into git.''',
              envvar='ROSETTA_CATALOG',
              show_default=True)
@click.option('-ca', '--catalog-activity',
              default='./{CATALOG}-activity',
              type=click.Path(exists=False, file_okay=False, dir_okay=True),
              help='''Directory of local catalog-activity files (runtime data based the catalog).
              The local catalog-activity DIRECTORY should NOT be checked into git,
              as it holds runtime data like logs, call histories, etc.''',
              envvar='ROSETTA_CATALOG_ACTIVITY',
              show_default=True)
@click.option('-v', '--verbose',
              count=True,
              help='Enable verbose output.',
              envvar='ROSETTA_VERBOSE')
@click.pass_context
def main(ctx, catalog, catalog_activity, verbose):
    """A command line tool for Rosetta."""
    ctx.obj = ctx.obj or {
        'catalog': catalog,                # Ex: "./catalog".
        'catalog_activity': catalog_activity
            .replace('{CATALOG}', catalog) # Ex: "./{CATALOG}-activity" => "././catalog-activity".
            .replace('/./', '/'),          # Ex: "././catalog-activity" => "./catalog-activity".
        'verbose': verbose
    }


@main.command()
@click.pass_context
def clean(ctx):
    """Clean up generated files, etc."""
    cmd_clean(ctx.obj)


@main.command()
@click.pass_context
def env(ctx):
    """Print this tool's env or configuration variables as JSON."""
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
              help='Embedding model when building the catalog file.',
              show_default=True)
@click.pass_context
def index(ctx, source_dirs, embedding_model):
    """Walk directory tree source files to build a catalog file.

    Source files scanned include *.py, *.sqlpp, *.yaml, etc."""

    # TODO: The index command should default to the '.' directory / current directory.
    # TODO: The index command should ignore the '.git' subdirectory.
    # TODO: The index command should ignore whatever's in the '.gitignore' file.

    cmd_index(ctx.obj, source_dirs=source_dirs, embedding_model=embedding_model)


@main.command()
@click.option('-em', '--embedding-model', 'embedding_models',
              multiple=True,
              default=[DEFAULT_EMBEDDING_MODEL],
              help='Embedding models to download and cache.',
              show_default=True)
@click.pass_context
def init(ctx, embedding_models):
    """Initialize the environment (e.g., download & cache models, etc)."""
    cmd_init_local(ctx.obj, embedding_models)


@main.command()
@click.pass_context
def publish(ctx):
    """Publish the catalog to a database."""
    cmd_publish(ctx.obj)


@main.command()
@click.pass_context
def status(ctx):
    """Show the status of the catalog."""
    cmd_status(ctx.obj)


@main.command()
@click.pass_context
def version(ctx):
    """Show the version of this tool."""
    cmd_version()


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
