import core.catalog.directory
import gitignore_parser

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
DEFAULT_MODEL_CACHE_FOLDER = ".model-cache"
DEFAULT_CATALOG_FOLDER = ".agent-catalog"
DEFAULT_ACTIVITY_FOLDER = ".agent-activity"
DEFAULT_LLM_ACTIVITY_NAME = "llm-activity.log"
DEFAULT_TOOL_CATALOG_NAME = "tool-catalog.json"
DEFAULT_PROMPT_CATALOG_NAME = "prompt-catalog.json"
DEFAULT_META_CATALOG_NAME = "meta.json"
DEFAULT_WEB_HOST_PORT = "127.0.0.1:5555"
DEFAULT_MAX_ERRS = 10
DEFAULT_VERBOSITY_LEVEL = 0
DEFAULT_SCAN_DIRECTORY_OPTS = core.catalog.directory.ScanDirectoryOpts(
    unwanted_patterns=frozenset([".git", "*__pycache__*", "*.lock", "*.toml", "*.md"]),
    ignore_file_name=".gitignore",
    ignore_file_parser_factory=gitignore_parser.parse_gitignore,
)
DEFAULT_CATALOG_NAME = "-catalog.json"
DEFAULT_META_COLLECTION_NAME = "_metadata"
DEFAULT_CATALOG_COLLECTION_NAME = "_catalog"
DEFAULT_CATALOG_SCOPE = "agent_catalog"
DEFAULT_CATALOG_SCHEMA_VERSION = "0_0_0"

__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_MODEL_CACHE_FOLDER",
    "DEFAULT_CATALOG_FOLDER",
    "DEFAULT_ACTIVITY_FOLDER",
    "DEFAULT_LLM_ACTIVITY_NAME",
    "DEFAULT_TOOL_CATALOG_NAME",
    "DEFAULT_PROMPT_CATALOG_NAME",
    "DEFAULT_META_CATALOG_NAME",
    "DEFAULT_WEB_HOST_PORT",
    "DEFAULT_MAX_ERRS",
    "DEFAULT_SCAN_DIRECTORY_OPTS",
    "DEFAULT_CATALOG_NAME",
    "DEFAULT_META_COLLECTION_NAME",
    "DEFAULT_CATALOG_COLLECTION_NAME",
    "DEFAULT_CATALOG_SCOPE",
    "DEFAULT_CATALOG_SCHEMA_VERSION",
]
