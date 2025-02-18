import langchain_core.embeddings
import langchain_core.language_models
import langchain_couchbase
import typing

from .options import CacheOptions
from .setup import setup_exact_cache
from .setup import setup_semantic_cache


def cache(
    chat_model: langchain_core.language_models.BaseChatModel,
    kind: typing.Literal["exact", "semantic"],
    options: CacheOptions,
    embeddings: langchain_core.embeddings.Embeddings = None,
):
    """A method to attach a Couchbase-backed exact or semantic cache to a ChatModel.

    :param chat_model: The LangChain chat model to cache responses for.
    :param kind: The type of cache to attach to the chat model.
    :param options: The options to use when attaching a cache to the chat model.
    :param embeddings: The embeddings to use when attaching a 'semantic' cache to the chat model.
    :return: The same LangChain chat model that was passed in, but with a cache attached.
    """
    if kind.lower() == "exact":
        setup_exact_cache(options)
        llm_cache = langchain_couchbase.cache.CouchbaseCache(
            cluster=options.cluster,
            bucket_name=options.bucket,
            scope_name=options.scope,
            collection_name=options.collection,
            ttl=options.ttl,
        )
        chat_model.cache = llm_cache
    elif kind.lower() == "semantic":
        setup_semantic_cache(options, embeddings)
        llm_cache = langchain_couchbase.cache.CouchbaseSemanticCache(
            cluster=options.cluster,
            embedding=embeddings,
            bucket_name=options.bucket,
            scope_name=options.scope,
            collection_name=options.collection,
            index_name=options.index_name,
            score_threshold=options.score_threshold,
            ttl=options.ttl,
        )
        chat_model.cache = llm_cache
    return chat_model
