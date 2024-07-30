import json
import pathlib

import click
import dotenv

from .action import *


# TODO: Should we load from ".env.rosetta"?
# TODO: Or, perhaps even stage specific, like from ".env.rosetta.prod"?
dotenv.load_dotenv()


default_hd = str((pathlib.Path(DEFAULT_OUTPUT_DIR) / DEFAULT_HISTORY_DIR).absolute())


@click.group(epilog='See: https://docs.couchbase.com for more information.')
@click.option('-c', '--catalog',
              default='./catalog',
              help='Directory of catalog files.',
              envvar='ROSETTA_CATALOG')
@click.option('-v', '--verbose',
              is_flag=True,
              help='Enable verbose output.',
              envvar='ROSETTA_VERBOSE')
@click.pass_context
def main(ctx, catalog, verbose):
    """A command line tool for Rosetta."""
    ctx.obj = ctx.obj or {}
    ctx.obj['catalog'] = catalog
    ctx.obj['verbose'] = verbose


@main.command()
@click.option('-hd', '--history-dir',
              default=default_hd,
              help=f'Directory of processing history to clean (default: {default_hd}).')
@click.pass_context
def clean(ctx, history_dir):
    """Clean up generated files, etc."""

    tool_catalog_file = ctx.obj['catalog'] + '/tool_catalog.json'
    prompt_catalog_file = ctx.obj['catalog'] + '/prompt_catalog.json'

    cmd_clean_local(tool_catalog_file=tool_catalog_file,
                    prompt_catalog_file=prompt_catalog_file,
                    history_dir=history_dir)


@main.command()
@click.pass_context
def env(ctx):
    """Print this tool's env or configuration variables as JSON."""
    cmd_env(ctx.obj)


@main.command()
@click.pass_context
def publish(ctx):
    """Find tools, prompts, etc. from the catalog."""
    cmd_find(ctx.obj)


@main.command()
@click.argument('source_dirs', nargs=-1, required=True)
@click.option('-em', '--embedding-model',
              default=DEFAULT_EMBEDDING_MODEL,
              help=f'Embedding model when building the catalog file (default: {DEFAULT_EMBEDDING_MODEL}).')
@click.pass_context
def index(ctx, source_dirs, embedding_model):
    """Walk directory tree source files to build a catalog file.

    Source files scanned include *.py, *.sqlpp, *.yaml, etc."""

    tool_catalog_file = ctx.obj['catalog'] + '/tool_catalog.json'

    cmd_index_local(tool_dirs=source_dirs,
                    tool_catalog_file=tool_catalog_file,
                    embedding_model=embedding_model)


@main.command()
@click.option('-em', '--embedding-model',
              multiple=True,
              default=[DEFAULT_EMBEDDING_MODEL],
              help=f'Embedding models to download and cache (default: {DEFAULT_EMBEDDING_MODEL}).')
@click.option('-hd', '--history-dir',
              default=default_hd,
              help=f'Directory for processing history (default: {default_hd}).')
@click.pass_context
def init(ctx, embedding_models, history_dir):
    """Initialize the environment (e.g., download & cache models, etc)."""
    cmd_init_local(embedding_models=embedding_models,
                   output_dir=ctx.obj['catalog'],
                   history_dir=history_dir)


@main.command()
@click.pass_context
def publish(ctx):
    """Publish the catalog to a database."""
    cmd_publish(ctx.obj)


@main.command()
@click.pass_context
def status(ctx):
    """Print the status the catalog."""
    cmd_status(ctx.obj)


@main.command()
@click.pass_context
def version(ctx):
    """Print the version of this tool."""
    cmd_version()


@main.command()
@click.option('--host-port',
              default=DEFAULT_WEB_HOST_PORT,
              envvar='ROSETTA_WEB_HOST_PORT',
              help=f'The host:port to listen on (default: {DEFAULT_WEB_HOST_PORT}).')
@click.option('--debug/--no-debug',
              envvar='ROSETTA_WEB_DEBUG',
              default=True,
              help='Debug mode (default: True).')
@click.pass_context
def web(ctx, host_port, debug):
    """Start local web server."""
    cmd_web(ctx.obj, host_port, debug)


if __name__ == '__main__':
    main()
