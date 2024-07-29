import pathlib
import os
import shutil
import couchbase.auth
import logging

logger = logging.getLogger(__name__)


def cmd_clean_local(tool_catalog_file: str, prompt_catalog_file: str, history_dir: str, **_):
    tool_catalog_path = pathlib.Path(tool_catalog_file)
    prompt_catalog_path = pathlib.Path(prompt_catalog_file)
    history_path = pathlib.Path(history_dir)

    # Handle our tool catalog...
    if tool_catalog_path.exists():
        if not tool_catalog_path.is_file():
            logger.warning('Non-file specified for tool_catalog_file! No deletion action has occurred.')
        else:
            os.remove(tool_catalog_path.absolute())
    else:
        logger.debug('tool_catalog_file does not exist. No deletion action has occurred.')

    # ...and our prompt catalog.
    if prompt_catalog_path.exists():
        if prompt_catalog_path.exists():
            if not prompt_catalog_path.is_file():
                logger.warning('Non-file specified for prompt_catalog_file! No deletion action has occurred.')
            else:
                os.remove(prompt_catalog_path.absolute())
        else:
            logger.debug('prompt_catalog_file does not exist. No deletion action has occurred.')

    # TODO (GLENN): Be a little more conservative here...
    if history_path.exists():
        if not history_path.is_dir():
            logger.warning('Non-directory specified for messages_dir!')
            os.remove(history_path.absolute())
        else:
            shutil.rmtree(history_path.absolute())
    else:
        logger.debug('history_dir does not exist. No deletion action has occurred for history_dir.')


# TODO (GLENN): Define a 'clean' action for a Couchbase collection.
def cmd_clean_couchbase(conn_string: str, authenticator: couchbase.auth.Authenticator, **_):
    pass
