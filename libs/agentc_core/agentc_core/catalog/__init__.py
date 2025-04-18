from .catalog import Catalog
from .implementations.base import CatalogBase
from .implementations.base import SearchResult
from .implementations.chain import CatalogChain
from .implementations.db import CatalogDB
from .implementations.mem import CatalogMem

__all__ = ["Catalog", "CatalogMem", "CatalogDB", "CatalogBase", "CatalogChain", "SearchResult"]

# Newer versions of the agentc_core library / tools might be able to read and/or write older catalog schema versions
# of data which were persisted into the local catalog and/or into the database.
#
# If there's an incompatible catalog schema enhancement as part of the development of a next, upcoming release, the
# latest __version__ should be bumped before the release.
__version__ = "0.0.0"
