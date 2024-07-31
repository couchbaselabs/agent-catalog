import logging
import os
import pathlib
import shutil

import couchbase.auth
import flask

logger = logging.getLogger(__name__)


def clean_local(ctx):
    tool_catalog_file = ctx['catalog'] + '/tool_catalog.json'
    prompt_catalog_file = ctx['catalog'] + '/prompt_catalog.json'
    catalog_activity_dir = ctx['catalog_activity']

    for x in [tool_catalog_file, prompt_catalog_file, catalog_activity_dir]:
        if not x or not os.path.exists(x):
            logger.warning('Skipping file/directory that does not exist: %s', x)
            continue

        x_path = pathlib.Path(x)

        if x_path.is_file():
            os.remove(x_path.absolute())
        elif x_path.is_dir():
            shutil.rmtree(x_path.absolute())


# TODO (GLENN): Define a 'clean' action for a Couchbase collection.
def clean_couchbase(ctx, conn_string: str, authenticator: couchbase.auth.Authenticator, **_):
    pass


def cmd_clean(ctx):
    if True: # TODO: Should check cmd-line flags on whether to clean local.
        clean_local(ctx)

    if False: # TODO: Should check cmd-line flags on whether to clean database.
        clean_couchbase(ctx, "TODO", None)


blueprint = flask.Blueprint('clean', __name__)

@blueprint.route('/clean', methods=['POST'])
def route_clean():
    # TODO: Check creds as it's destructive.

    ctx = flask.current_app.config['ctx']

    if True: # TODO: Should check REST args on whether to clean local.
        clean_local(ctx, None)

    if False: # TODO: Should check REST args on whether to clean database.
        clean_couchbase(ctx, "TODO", None)

    return "OK" # TODO.

