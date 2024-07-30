# Our commands...
from .clean import (
    cmd_clean_couchbase,
    cmd_clean_local
)
from .env import (
    cmd_env
)
from .find import (
    cmd_find
)
from .index import (
    cmd_index_couchbase,
    cmd_index_local
)
from .init import (
    cmd_init_couchbase,
    cmd_init_local
)
from .publish import (
    cmd_publish
)
from .status import (
    cmd_status
)
from .version import (
    cmd_version
)
from .web import (
    cmd_web
)


def register_blueprints(app):
    # TODO: app.register_blueprint(clean.blueprint)
    # TODO: app.register_blueprint(find.blueprint)
    # TODO: app.register_blueprint(index.blueprint)
    # TODO: app.register_blueprint(init.blueprint)
    # TODO: app.register_blueprint(publish.blueprint)
    # TODO: app.register_blueprint(status.blueprint)

    app.register_blueprint(env.blueprint)
    app.register_blueprint(version.blueprint)


# ...and our defaults.
DEFAULT_OUTPUT_DIR = '.out'
DEFAULT_HISTORY_DIR = 'history'
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L12-v2'
DEFAULT_WEB_HOST_PORT = '127.0.0.1:5555'
