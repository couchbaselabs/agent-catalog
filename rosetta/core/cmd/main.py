import pathlib
import click

from .action import *

@click.group()
def main():
    """A command line interface for Rosetta."""
    pass

@main.command()
@click.option('-sm', '--sentence-models',
              multiple=True,
              default=['sentence-transformers/all-MiniLM-L12-v2'],
              help='SBERT models to download ahead of time.')
@click.option('-od', '--output-directory',
              default=DEFAULT_OUTPUT_DIRECTORY,
              help='Location of the output directory to initialize (for non-CB-backed agents).')
@click.option('-hist', '--history-directory',
              default=str((pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_HISTORY_DIRECTORY).absolute()),
              help='Place to store the agent action history (relative to the output_directory).')
def init(sentence_models, output_directory, history_directory):
    """Initialize the runtime environment (e.g., install sentence_transformers models)."""
    cmd_initialize_local(sentence_models=sentence_models,
                         output_directory=output_directory,
                         history_directory=history_directory)

@main.command()
@click.option('-cf', '--catalog-file',
              default=str((pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_CATALOG_FILENAME).absolute()),
              help='Name of the tool catalog to remove.')
@click.option('-hd', '--history-dir',
              default=str((pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_HISTORY_DIRECTORY).absolute()),
              help='Location of any agent messages to remove.')
def clean(catalog_file, history_dir):
    """Delete all index-time / runtime artifacts."""
    cmd_clean_local(catalog_file=catalog_file, history_dir=history_dir)

@main.command()
@click.argument('tool_dirs', nargs=-1, required=True)
@click.option('-cf', '--catalog-file',
              default=str((pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_CATALOG_FILENAME).absolute()),
              help='Name of the tool catalog to-be-generated (relative to the output directory).')
@click.option('-em', '--embedding-model',
              default='sentence-transformers/all-MiniLM-L12-v2',
              help='Embedding model to use when building the tool catalog.')
def index(tool_dirs, catalog_file, embedding_model):
    """Walk one or more directories and build a catalog from Python source and descriptor files (*.sqlpp and *.yaml)."""
    cmd_index_local(tool_dirs=tool_dirs,
                    catalog_file=catalog_file,
                    embedding_model=embedding_model)

@main.command()
def version():
    """Print the version of this tool."""
    cmd_version()

@main.command()
def web():
    """Start a web server."""
    cmd_web()

if __name__ == '__main__':
    main()
