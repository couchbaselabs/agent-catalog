import argparse
import pathlib

# We will just pull everything from action into here.
from .action import *

parser = argparse.ArgumentParser(
    description='A command line interface for Rosetta.'
)
subparsers = parser.add_subparsers(required=True)


def _add_init_parser():
    init_parser = subparsers.add_parser(
        name='init',
        description='Initialize the runtime environment (e.g., install sentence_transformers models).'
    )
    init_parser.add_argument(
        '-sm', '--sentence_models',
        nargs='+',
        type=str,
        default=['sentence-transformers/all-MiniLM-L12-v2'],
        help='SBERT models to download ahead of time.'
    )
    init_parser.add_argument(
        '-od', '--output_directory',
        type=str,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help='Location of the output directory to initialize (for non-CB-backed agents).'
    )
    init_parser.add_argument(
        '-hist', '--history_directory',
        type=str,
        default=(pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_HISTORY_DIRECTORY).absolute(),
        help='Place to store the agent action history (relative to the output_directory).'
    )
    init_parser.set_defaults(func=cmd_initialize_local)


def _add_clean_parser():
    clean_parser = subparsers.add_parser(
        name='clean',
        description='Delete all index-time / runtime artifacts.'
    )
    clean_parser.add_argument(
        '-cf', '--catalog_file',
        type=str,
        default=(pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_CATALOG_FILENAME).absolute(),
        help='Name of the tool catalog to remove.'
    )
    clean_parser.add_argument(
        '-hd', '--history_dir',
        type=str,
        default=(pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_HISTORY_DIRECTORY).absolute(),
        help='Location of any agent messages to remove.'
    )
    clean_parser.set_defaults(func=cmd_clean_local)


def _add_index_parser():
    index_parser = subparsers.add_parser(
        name='index',
        description='Walk one or more directories and build a tool catalog from Python tools and descriptor '
                    'files (*.sqlpp and *.yaml).'
    )
    index_parser.add_argument(
        'tool_dirs',
        type=str,
        nargs='+',
        help='Location of the tools (*.py) and tool descriptors (*.sqlpp and *.yaml) to index.'
    )
    index_parser.add_argument(
        '-cf', '--catalog_file',
        type=str,
        default=(pathlib.Path(DEFAULT_OUTPUT_DIRECTORY) / DEFAULT_CATALOG_FILENAME).absolute(),
        help='Name of the tool catalog to-be-generated (relative to the output directory).'
    )
    index_parser.add_argument(
        '-em', '--embedding_model',
        type=str,
        default='sentence-transformers/all-MiniLM-L12-v2',
        help='Embedding model to use when building the tool catalog.'
    )
    index_parser.set_defaults(func=cmd_index_local)


def main():
    _add_init_parser()
    _add_clean_parser()
    _add_index_parser()
    arguments = parser.parse_args()
    arguments.func(**vars(arguments))


if __name__ == '__main__':
    main()
