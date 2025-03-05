import gitignore_parser

DEFAULT_EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L12-v2"
DEFAULT_MODEL_CACHE_FOLDER = ".model-cache"
DEFAULT_CATALOG_FOLDER = ".agent-catalog"
DEFAULT_CATALOG_SCOPE = "agent_catalog"
DEFAULT_CATALOG_METADATA_COLLECTION = "metadata"
DEFAULT_CATALOG_TOOL_COLLECTION = "tools"
DEFAULT_CATALOG_PROMPT_COLLECTION = "prompts"
DEFAULT_ACTIVITY_SCOPE = "agent_activity"
DEFAULT_ACTIVITY_LOG_COLLECTION = "logs"
DEFAULT_AUDIT_TESTS_COLLECTION = "tests"
DEFAULT_HTTP_FTS_PORT_NUMBER = "8094"
DEFAULT_HTTPS_FTS_PORT_NUMBER = "18094"
DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER = "8091"
DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER = "18091"
DEFAULT_ITEM_DESCRIPTION_MAX_LEN = 256
DEFAULT_ACTIVITY_FOLDER = ".agent-activity"
DEFAULT_ACTIVITY_FILE = "activity.log"
DEFAULT_TOOL_CATALOG_FILE = "tools.json"
DEFAULT_PROMPT_CATALOG_FILE = "prompts.json"
DEFAULT_WEB_HOST_PORT = "127.0.0.1:5555"
DEFAULT_MAX_ERRS = 10
DEFAULT_CLUSTER_WAIT_UNTIL_READY_SECONDS = 5
DEFAULT_CLUSTER_DDL_RETRY_ATTEMPTS = 3
DEFAULT_CLUSTER_DDL_RETRY_WAIT_SECONDS = 5
DEFAULT_VERBOSITY_LEVEL = 0
DEFAULT_SCAN_DIRECTORY_OPTS = dict(
    unwanted_patterns=frozenset([".git", "*__pycache__*", "*.lock", "*.toml", "*.md"]),
    ignore_file_names=[".gitignore", ".agentcignore"],
    ignore_file_parser_factory=gitignore_parser.parse_gitignore,
)

__all__ = [
    "DEFAULT_EMBEDDING_MODEL_NAME",
    "DEFAULT_MODEL_CACHE_FOLDER",
    "DEFAULT_CATALOG_FOLDER",
    "DEFAULT_ACTIVITY_FOLDER",
    "DEFAULT_ACTIVITY_FILE",
    "DEFAULT_TOOL_CATALOG_FILE",
    "DEFAULT_PROMPT_CATALOG_FILE",
    "DEFAULT_WEB_HOST_PORT",
    "DEFAULT_MAX_ERRS",
    "DEFAULT_SCAN_DIRECTORY_OPTS",
    "DEFAULT_CATALOG_SCOPE",
    "DEFAULT_CATALOG_METADATA_COLLECTION",
    "DEFAULT_CATALOG_TOOL_COLLECTION",
    "DEFAULT_CATALOG_PROMPT_COLLECTION",
    "DEFAULT_ACTIVITY_SCOPE",
    "DEFAULT_ACTIVITY_LOG_COLLECTION",
    "DEFAULT_AUDIT_TESTS_COLLECTION",
    "DEFAULT_HTTP_FTS_PORT_NUMBER",
    "DEFAULT_HTTPS_FTS_PORT_NUMBER",
    "DEFAULT_MODEL_CACHE_FOLDER",
    "DEFAULT_ITEM_DESCRIPTION_MAX_LEN",
    "DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER",
    "DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER",
]
