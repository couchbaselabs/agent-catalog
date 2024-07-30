import logging
import os
import pathlib
import shutil

import couchbase.auth

logger = logging.getLogger(__name__)


def clean_local(ctx, history_dir: str):
    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'
    prompt_catalog_file = ctx['catalog'] + '/prompt_catalog.json'

    for x in [tool_catalog_file, prompt_catalog_file, history_dir]:
        if not os.path.exists(x):
            logger.warning('Skipping file/directory that does not exist: %s', x)

        x_path = pathlib.Path(x)

        if x_path.is_file():
            os.remove(x_path.absolute())
        elif x.is_dir():
            shutil.rmtree(x_path.absolute())


# TODO (GLENN): Define a 'clean' action for a Couchbase collection.
def clean_couchbase(ctx, conn_string: str, authenticator: couchbase.auth.Authenticator, **_):
    pass


def cmd_clean(ctx, history_dir: str, **_):
    if True: # TODO: Should check cmd-line flags on whether to clean local.
        clean_local(ctx, history_dir)

    if False: # TODO: Should check cmd-line flags on whether to clean database.
        clean_couchbase(ctx, conn_str="TODO")

