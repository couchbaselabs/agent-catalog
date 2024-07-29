# Our commands...
from .clean import (
    cmd_clean_couchbase,
    cmd_clean_local
)
from .init import (
    cmd_init_couchbase,
    cmd_init_local
)
from .index import (
    cmd_index_couchbase,
    cmd_index_local
)
from .version import (
    cmd_version
)
from .web import (
    cmd_web
)


def register_blueprints(app):
    # app.register_blueprint(clean.blueprint)
    # app.register_blueprint(init.blueprint)
    # app.register_blueprint(index.blueprint)
    app.register_blueprint(version.blueprint)


# ...and our defaults.
DEFAULT_OUTPUT_DIR = '.out'
DEFAULT_HISTORY_DIR = 'history'
DEFAULT_CATALOG_SUFFIX = '_catalog.json'
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L12-v2'
DEFAULT_WEB_HOST_PORT = '127.0.0.1:5555'
