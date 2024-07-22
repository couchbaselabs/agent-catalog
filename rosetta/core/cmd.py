import argparse
import typing
import pathlib
import shutil
import logging
import os

logger = logging.getLogger(__name__)


# TODO (GLENN): Define an 'init' action for Capella.
def cmd_initialize(sentence_models: typing.List[str], **_):
    import sentence_transformers

    for model in sentence_models:
        sentence_transformers.SentenceTransformer(model)


# TODO (GLENN): Define a 'clean' action for Capella.
def cmd_clean(build_dir: str, catalog_file: str, messages_dir: str, **_):
    build_path = pathlib.Path(build_dir)
    catalog_path = pathlib.Path(catalog_file)
    messages_path = pathlib.Path(messages_dir)

    # TODO (GLENN): Be a little more conservative here...
    if build_path.exists():
        if not build_path.is_dir():
            logger.warning('Non-directory specified for build_dir!')
            os.remove(build_path.absolute())
        else:
            shutil.rmtree(build_path.absolute())
    else:
        logger.debug('build_dir does not exist. No deletion action has occurred for build_dir.')

    # TODO (GLENN): This will change when we expand to more than just tools.
    if catalog_path.exists():
        if not catalog_path.is_file():
            logger.warning('Non-file specified for catalog_file! No deletion action has occurred for catalog_file.')
        else:
            os.remove(catalog_path.absolute())
    else:
        logger.debug('catalog_file does not exist. No deletion action has occurred for catalog_file.')

    # TODO (GLENN): Be a little more conservative here...
    if messages_path.exists():
        if not messages_path.is_dir():
            logger.warning('Non-directory specified for messages_dir!')
            os.remove(messages_path.absolute())
        else:
            shutil.rmtree(messages_path.absolute())
    else:
        logger.debug('messages_dir does not exist. No deletion action has occurred for messages_dir.')


def cmd_index(tool_dirs: typing.List[str], catalog_file: str, embedding_model: str, **_):
    import rosetta.core.tools
    import sentence_transformers

    # TODO (GLENN): Define an 'index' action for Capella.
    rosetta.core.tools.LocalRegistrar(
        catalog_file=pathlib.Path(catalog_file),
        embedding_model=sentence_transformers.SentenceTransformer(embedding_model)
    ).index([pathlib.Path(p) for p in tool_dirs])


def main():
    parser = argparse.ArgumentParser(
        description='A command line interface for Rosetta.'
    )
    subparsers = parser.add_subparsers(required=True)

    # Define the 'rosetta init' command.
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
    init_parser.set_defaults(func=cmd_initialize)

    # Define the 'rosetta clean' command.
    clean_parser = subparsers.add_parser(
        name='clean',
        description='Delete all compile-time / register-time / runtime artifacts.'
    )
    clean_parser.add_argument(
        '-bd', '--build_dir',
        nargs='*',
        type=str,
        default='.out',
        help='Location of the generated tools to remove.'
    )
    clean_parser.add_argument(
        '-cf', '--catalog_file',
        type=str,
        default='.out/tool_catalog.json',
        help='Name of the tool catalog to remove.'
    )
    clean_parser.add_argument(
        '-md', '--messages_dir',
        type=str,
        default='.out',
        help='Location of any agent messages to remove.'
    )
    clean_parser.set_defaults(func=cmd_clean)

    # Define the 'rosetta index' command.
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
        default='.out/tool_catalog.json',
        help='Name of the tool catalog to-be-generated.'
    )
    index_parser.add_argument(
        '-em', '--embedding_model',
        type=str,
        default='sentence-transformers/all-MiniLM-L12-v2',
        help='Embedding model to use when building the tool catalog.'
    )
    index_parser.set_defaults(func=cmd_index)

    arguments = parser.parse_args()
    arguments.func(**vars(arguments))


if __name__ == '__main__':
    main()
