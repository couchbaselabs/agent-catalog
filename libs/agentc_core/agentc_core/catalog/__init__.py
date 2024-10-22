from .catalog.base import LATEST_SNAPSHOT_VERSION
from .catalog.base import CatalogBase
from .catalog.base import SearchResult
from .catalog.chain import CatalogChain
from .catalog.db import CatalogDB
from .catalog.mem import CatalogMem

__all__ = ["CatalogMem", "CatalogDB", "CatalogBase", "CatalogChain", "SearchResult", "LATEST_SNAPSHOT_VERSION"]

# Newer versions of the agentc_core library / tools might be able to read and/or write older catalog schema versions
# of data which were persisted into the local catalog and/or into the database.
#
# If there's an incompatible catalog schema enhancement as part of the development of a next, upcoming release, the
# latest __version__ should be bumped before the release.
__version__ = "0.0.0"
