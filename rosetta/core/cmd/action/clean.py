import pathlib
import os
import shutil
import couchbase.auth
import logging

logger = logging.getLogger(__name__)


def cmd_clean_local(catalog_file: str, history_dir: str, **_):
    catalog_path = pathlib.Path(catalog_file)
    history_path = pathlib.Path(history_dir)

    # TODO (GLENN): This will change when we expand to more than just tools.
    if catalog_path.exists():
        if not catalog_path.is_file():
            logger.warning('Non-file specified for catalog_file! No deletion action has occurred for catalog_file.')
        else:
            os.remove(catalog_path.absolute())
    else:
        logger.debug('catalog_file does not exist. No deletion action has occurred for catalog_file.')

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
