# Our commands...
from .clean import (
    cmd_clean_couchbase,
    cmd_clean_local
)
from .init import (
    cmd_initialize_couchbase,
    cmd_initialize_local
)
from .index import (
    cmd_index_couchbase,
    cmd_index_local
)
from .version import (
    cmd_version
)

# ...and our defaults.
DEFAULT_OUTPUT_DIRECTORY = '.out'
DEFAULT_HISTORY_DIRECTORY = 'history'
DEFAULT_CATALOG_FILENAME = 'catalog.json'
