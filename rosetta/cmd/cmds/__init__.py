# Our commands...
from .clean import (
    cmd_clean
)
from .env import (
    cmd_env
)
from .find import (
    cmd_find
)
from .index import (
    cmd_index
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


# ...and our defaults.
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L12-v2'
DEFAULT_WEB_HOST_PORT = '127.0.0.1:5555'
