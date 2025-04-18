import langchain_core.embeddings
import os

from .options import CacheOptions
from agentc_core.config import Config
from agentc_core.remote.util.ddl import create_scope_and_collection
from agentc_core.remote.util.ddl import create_vector_index


def setup_exact_cache(options: CacheOptions):
    cb = options.Cluster().bucket(bucket_name=options.bucket)
    bucket_manager = cb.collections()
    msg, err = create_scope_and_collection(
        collection_manager=bucket_manager,
        scope=options.scope,
        collection=options.collection,
        ddl_retry_attempts=options.ddl_retry_attempts,
        ddl_retry_wait_seconds=options.ddl_retry_wait_seconds,
    )
    if err:
        raise ValueError(msg)


def setup_semantic_cache(options: CacheOptions, embeddings: langchain_core.embeddings.Embeddings):
    setup_exact_cache(options)

    # TODO (GLENN): Add this to the defaults.
    max_partition_env = os.getenv("AGENT_CATALOG_LANGCHAIN_CACHE_MAX_SOURCE_PARTITION")
    try:
        max_partition = int(max_partition_env) if max_partition_env is not None else 1024

    except Exception as e:
        # TODO (GLENN): We shouldn't be catching a broad exception here.
        raise ValueError(
            f"Cannot convert given value of max source partition to integer: {e}\n"
            f"Update the environment variable 'AGENT_CATALOG_LANGCHAIN_CACHE_MAX_SOURCE_PARTITION' to an integer value."
        ) from e

    index_partition_env = os.getenv("AGENT_CATALOG_LANGCHAIN_CACHE_INDEX_PARTITION")
    try:
        index_partition = int(index_partition_env) if index_partition_env is not None else None

    except Exception as e:
        # TODO (GLENN): We shouldn't be catching a broad exception here.
        raise ValueError(
            f"Cannot convert given value of index partition to integer: {e}\n"
            f"Update the environment variable 'AGENT_CATALOG_LANGCHAIN_CACHE_INDEX_PARTITION' to an integer value."
        ) from e

    config = Config(
        bucket=options.bucket,
        conn_string=options.conn_string,
        username=options.username,
        password=options.password.get_secret_value(),
        conn_root_certificate=options.conn_root_certificate,
        max_index_partition=max_partition,
        index_partition=index_partition,
    )

    _, err = create_vector_index(
        config,
        scope=options.scope,
        collection=options.collection,
        index_name=options.index_name,
        # To determine the dimension, we'll use the sample text "text".
        dim=len(embeddings.embed_query("text")),
    )
    if err:
        raise ValueError(err)
