import langchain_core.embeddings
import langchain_core.language_models
import langchain_couchbase
import typing

from .options import CacheOptions
from .setup import setup_exact_cache
from .setup import setup_semantic_cache


def initialize(
    kind: typing.Literal["exact", "semantic"],
    options: CacheOptions = None,
    embeddings: langchain_core.embeddings.Embeddings = None,
    **kwargs,
) -> None:
    """A function to create the collections and/or indexes required to use the :py:meth:`cache` function.

    .. card:: Function Description

        This function is a helper function for creating the default collection (and index, in the case of
        :python:`kind="semantic"`) required for the :py:meth:`cache` function.
        Below, we give a minimal working example of how to use this function to create a semantic cache backed by
        Couchbase.

        .. code-block:: python

            import langchain_openai
            import agentc_langchain.cache

            embeddings = langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")
            agentc_langchain.cache.initialize(
                kind="semantic",
                embeddings=embeddings
            )

            chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o")
            caching_chat_model = agentc_langchain.cache.cache(
                chat_model=chat_model,
                kind="semantic",
                embeddings=embeddings,
            )

            # Response #2 is served from the cache.
            response_1 = caching_chat_model.invoke("Hello there!")
            response_2 = caching_chat_model.invoke("Hello there!!")

    :param kind: The type of cache to attach to the chat model.
    :param embeddings: The embeddings to use when attaching a 'semantic' cache to the chat model.
    :param options: The options to use when attaching a cache to the chat model.
    :param kwargs: Keyword arguments to be forwarded to a :py:class:`CacheOptions` constructor (ignored if options is
                   present).
    """
    if options is None:
        options = CacheOptions(**kwargs)
    options.create_if_not_exists = True
    if kind.lower() == "exact":
        setup_exact_cache(options)
    elif kind.lower() == "semantic":
        setup_semantic_cache(options, embeddings)
    else:
        raise ValueError("Illegal kind specified! 'kind' must be 'exact' or 'semantic'.")


def cache(
    chat_model: langchain_core.language_models.BaseChatModel,
    kind: typing.Literal["exact", "semantic"],
    embeddings: langchain_core.embeddings.Embeddings = None,
    options: CacheOptions = None,
    **kwargs,
) -> langchain_core.language_models.BaseChatModel:
    """A function to attach a Couchbase-backed exact or semantic cache to a ChatModel.

    .. card:: Function Description

        This function is used to set the ``.cache`` property of LangChain ``ChatModel`` instances.
        For all options related to this Couchbase-backed cache, see :py:class:`CacheOptions`.

        Below, we illustrate a minimal working example of how to use this function to store and retrieve LLM responses
        via exact prompt matching:

        .. code-block:: python

            import langchain_openai
            import agentc_langchain.cache

            chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o")
            caching_chat_model = agentc_langchain.cache.cache(
                chat_model=chat_model,
                kind="exact",
                create_if_not_exists=True
            )

            # Response #2 is served from the cache.
            response_1 = caching_chat_model.invoke("Hello there!")
            response_2 = caching_chat_model.invoke("Hello there!")

        To use this function to store and retrieve LLM responses via semantic similarity, use the
        :python:`kind="semantic"` argument with an :py:class:`langchain_core.embeddings.Embeddings` instance:

        .. code-block:: python

            import langchain_openai
            import agentc_langchain.cache

            chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o")
            embeddings = langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")
            caching_chat_model = agentc_langchain.cache.cache(
                chat_model=chat_model,
                kind="semantic",
                embeddings=embeddings,
                create_if_not_exists=True
            )

            # Response #2 is served from the cache.
            response_1 = caching_chat_model.invoke("Hello there!")
            response_2 = caching_chat_model.invoke("Hello there!!")

        By default, the Couchbase initialization of the cache is separate from the cache's usage (storage and
        retrieval).
        To explicitly initialize the cache yourself, use the :py:meth:`initialize` method.

    .. seealso::

        This method uses the ``langchain_couchbase.cache.CouchbaseCache`` and
        ``langchain_couchbase.cache.CouchbaseSemanticCache`` classes from the ``langchain_couchbase`` package.
        See `here <https://api.python.langchain.com/en/latest/couchbase/cache.html>`__ for more details.

    :param chat_model: The LangChain chat model to cache responses for.
    :param kind: The type of cache to attach to the chat model.
    :param embeddings: The embeddings to use when attaching a 'semantic' cache to the chat model.
    :param options: The options to use when attaching a cache to the chat model.
    :param kwargs: Keyword arguments to be forwarded to a :py:class:`CacheOptions` constructor (ignored if options is
                   present).
    :return: The same LangChain chat model that was passed in, but with a cache attached.
    """
    if options is None:
        options = CacheOptions(**kwargs)
    if options.create_if_not_exists:
        initialize(kind=kind, options=options, embeddings=embeddings)

    # Attach our cache to the chat model.
    if kind.lower() == "exact":
        llm_cache = langchain_couchbase.cache.CouchbaseCache(
            cluster=options.Cluster(),
            bucket_name=options.bucket,
            scope_name=options.scope,
            collection_name=options.collection,
            ttl=options.ttl,
        )
        chat_model.cache = llm_cache
    elif kind.lower() == "semantic":
        llm_cache = langchain_couchbase.cache.CouchbaseSemanticCache(
            cluster=options.Cluster(),
            embedding=embeddings,
            bucket_name=options.bucket,
            scope_name=options.scope,
            collection_name=options.collection,
            index_name=options.index_name,
            score_threshold=options.score_threshold,
            ttl=options.ttl,
        )
        chat_model.cache = llm_cache
    else:
        raise ValueError("Illegal kind specified! 'kind' must be 'exact' or 'semantic'.")
    return chat_model
