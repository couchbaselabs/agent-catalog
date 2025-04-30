import acouchbase.cluster
import langchain_core.runnables
import langgraph.checkpoint.base
import langgraph.checkpoint.serde.base
import langgraph.checkpoint.serde.types
import langgraph_checkpointer_couchbase
import time
import typing

from .options import CheckpointOptions
from agentc_core.remote.util.ddl import create_scope_and_collection


def initialize(options: CheckpointOptions = None, **kwargs) -> None:
    """A function to create the collections required to use the checkpoint savers in this module.

    .. card:: Function Description

        This function is a helper function for creating the default collections (the thread and tuple collections)
        required for the :py:class:`CheckpointSaver` and :py:class`AsyncCheckpointSaver` classes.
        Below, we give a minimal working example of how to use this function to create these collections.

        .. code-block:: python

            import langchain_openai
            import langgraph.prebuilt
            import agentc_langgraph.state

            # Initialize our collections.
            agentc_langgraph.state.initialize()

            # Pass our checkpoint saver to the create_react_agent method.
            chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
            agent = langgraph.prebuilt.create_react_agent(
                model=chat_model,
                tools=list(),
                checkpointer=CheckpointSaver()
            )
            config = {"configurable": {"thread_id": "1"}}
            agent.invoke({"messages": [("human", "Hello there!")]}, config)

    :param options: The options to use when saving checkpoints to Couchbase.
    :param kwargs: Keyword arguments to be forwarded to a :py:class:`CheckpointOptions` constructor (ignored if
                   options is present).
    """
    if options is None:
        options = CheckpointOptions(**kwargs)
    cluster = options.Cluster()
    cb = cluster.bucket(bucket_name=options.bucket)
    bucket_manager = cb.collections()
    msg, err = create_scope_and_collection(
        collection_manager=bucket_manager,
        scope=options.scope,
        collection=options.checkpoint_collection,
        ddl_retry_attempts=options.ddl_retry_attempts,
        ddl_retry_wait_seconds=options.ddl_retry_wait_seconds,
    )
    if err:
        raise ValueError(msg)
    time.sleep(options.ddl_retry_wait_seconds)

    msg, err = create_scope_and_collection(
        collection_manager=bucket_manager,
        scope=options.scope,
        collection=options.tuple_collection,
        ddl_retry_attempts=options.ddl_retry_attempts,
        ddl_retry_wait_seconds=options.ddl_retry_wait_seconds,
    )
    if err:
        raise ValueError(msg)


class CheckpointSaver(langgraph.checkpoint.base.BaseCheckpointSaver):
    """Checkpoint saver class to persist LangGraph states in a Couchbase instance.

    .. card:: Class Description

        Instances of this class are used by LangGraph (passed in during :py:meth:`compile()` time)
        to save checkpoints of agent state.

        Below, we give a minimal working example of how to use this class with LangGraph's prebuilt ReAct agent.

        .. code-block:: python

            import langchain_openai
            import langgraph.prebuilt
            import agentc_langgraph.state

            # Pass our checkpoint saver to the create_react_agent method.
            chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
            agent = langgraph.prebuilt.create_react_agent(
                model=chat_model,
                tools=list(),
                checkpointer=CheckpointSaver(create_if_not_exists=True)
            )
            config = {"configurable": {"thread_id": "1"}}
            agent.invoke({"messages": [("human", "Hello!)]}, config)

        To use this method with Agent Catalog's :py:class:`agentc_langgraph.graph.GraphRunnable` class, pass the
        checkpoint saver to your workflow's ``compile()`` method (see the documentation for LangGraph's
        ``Graph.compile()`` method `here <https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.graph.Graph.compile>`__
        for more information.

        .. code-block:: python

            import langgraph.prebuilt
            import langgraph.graph
            import langchain_openai
            import langchain_core.messages
            import agentc_langgraph
            import agentc
            import typing

            class MyResearcherApp(agentc_langgraph.graph.GraphRunnable):
                def search_web(self, str: search_string) -> str:
                    ...

                def summarize_results(self, str: content) -> str:
                    ...

                def compile(self):
                    research_agent = langgraph.prebuilt.create_react_agent(
                        model=langchain_openai.ChatOpenAI(model="gpt-4o"),
                        tools=[self.search_web]
                    )
                    summary_agent = langgraph.prebuilt.create_react_agent(
                        model=langchain_openai.ChatOpenAI(model="gpt-4o"),
                        tools=[self.summarize_results]
                    )
                    workflow = langgraph.graph.StateGraph(agentc_langgraph.graph.State)
                    workflow.add_node("research_agent", research_agent)
                    workflow.add_node("summary_agent", summary_agent)
                    workflow.add_edge("research_agent", "summary_agent")
                    workflow.add_edge("summary_agent", langgraph.graph.END)
                    workflow.set_entry_point("research_agent")
                    checkpointer = agentc_langgraph.state.CheckpointSaver(create_if_not_exists=True)
                    return workflow.compile(checkpointer=checkpointer)

        .. tip::

            See `here <https://langchain-ai.github.io/langgraph/concepts/persistence/#checkpoints>`__ for more
            information about checkpoints in LangGraph.

        .. seealso::

            This class is a wrapper around the ``langgraph_checkpointer_couchbase.CouchbaseSaver`` class.
            See `here <https://pypi.org/project/langgraph-checkpointer-couchbase/>`__ for more information.

    """

    def __init__(
        self,
        options: CheckpointOptions = None,
        *,
        serde: typing.Optional[langgraph.checkpoint.serde.base.SerializerProtocol] = None,
        **kwargs,
    ):
        self.options: CheckpointOptions = options if options is not None else CheckpointOptions(**kwargs)
        if self.options.create_if_not_exists:
            initialize(self.options)

        # This class is mainly a wrapper around the CouchbaseSaver class below.
        self.sync_saver = langgraph_checkpointer_couchbase.CouchbaseSaver(
            cluster=self.options.Cluster(),
            bucket_name=self.options.bucket,
            scope_name=self.options.scope,
            checkpoints_collection_name=self.options.checkpoint_collection,
            checkpoint_writes_collection_name=self.options.tuple_collection,
        )
        self.sync_saver.bucket_name = f"`{self.options.bucket}`"
        self.sync_saver.scope_name = f"`{self.options.scope}`"
        super().__init__(serde=serde)

    def get(
        self, config: langchain_core.runnables.RunnableConfig
    ) -> typing.Optional[langgraph.checkpoint.base.Checkpoint]:
        return self.sync_saver.get(config=config)

    def get_tuple(
        self, config: langchain_core.runnables.RunnableConfig
    ) -> typing.Optional[langgraph.checkpoint.base.CheckpointTuple]:
        return self.sync_saver.get_tuple(config=config)

    def list(
        self,
        config: typing.Optional[langchain_core.runnables.RunnableConfig],
        *,
        filter: typing.Optional[dict[str, typing.Any]] = None,
        before: typing.Optional[langchain_core.runnables.RunnableConfig] = None,
        limit: typing.Optional[int] = None,
    ) -> typing.Iterator[langgraph.checkpoint.base.CheckpointTuple]:
        return self.sync_saver.list(config=config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: langchain_core.runnables.RunnableConfig,
        checkpoint: langgraph.checkpoint.base.Checkpoint,
        metadata: langgraph.checkpoint.base.CheckpointMetadata,
        new_versions: langgraph.checkpoint.base.ChannelVersions,
    ) -> langchain_core.runnables.RunnableConfig:
        return self.sync_saver.put(config=config, checkpoint=checkpoint, metadata=metadata, new_versions=new_versions)

    def put_writes(
        self,
        config: langchain_core.runnables.RunnableConfig,
        writes: typing.Sequence[tuple[str, typing.Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return self.sync_saver.put_writes(config=config, writes=writes, task_id=task_id)


# TODO (GLENN): This class currently doesn't work due to a bug upstream (in langgraph-checkpointer-couchbase).
#               We'll revisit this class later.
class AsyncCheckpointSaver(langgraph.checkpoint.base.BaseCheckpointSaver):
    @classmethod
    async def create(
        cls,
        options: CheckpointOptions = None,
        *,
        serde: typing.Optional[langgraph.checkpoint.serde.base.SerializerProtocol] = None,
        **kwargs,
    ) -> "AsyncCheckpointSaver":
        options: CheckpointOptions = options if options is not None else CheckpointOptions(**kwargs)
        if options.create_if_not_exists:
            initialize(options)

        # Connect to our cluster.
        cluster: acouchbase.cluster.Cluster = await options.AsyncCluster()
        saver: "AsyncCheckpointSaver" = AsyncCheckpointSaver(
            options=options,
            cluster=cluster,
            serde=serde,
        )

        # Connect to our bucket.
        saver.async_saver.bucket = cluster.bucket(options.bucket)
        await saver.async_saver.bucket.on_connect()

        # Finally, return our checkpoint saver.
        return saver

    def __init__(
        self,
        cluster: acouchbase.cluster.Cluster,
        options: CheckpointOptions = None,
        serde: typing.Optional[langgraph.checkpoint.serde.base.SerializerProtocol] = None,
        **kwargs,
    ):
        self.options: CheckpointOptions = options if options is not None else CheckpointOptions(**kwargs)
        if self.options.create_if_not_exists:
            initialize(self.options)

        # This class is mainly a wrapper around the CouchbaseSaver class below.
        self.async_saver = langgraph_checkpointer_couchbase.AsyncCouchbaseSaver(
            cluster=cluster,
            bucket_name=self.options.bucket,
            scope_name=self.options.scope,
            checkpoints_collection_name=self.options.checkpoint_collection,
            checkpoint_writes_collection_name=options.tuple_collection,
        )
        super().__init__(serde=serde)

    async def aget_tuple(
        self, config: langchain_core.runnables.RunnableConfig
    ) -> typing.Optional[langgraph.checkpoint.base.CheckpointTuple]:
        return await self.async_saver.aget_tuple(config=config)

    async def alist(
        self,
        config: typing.Optional[langchain_core.runnables.RunnableConfig],
        *,
        filter: typing.Optional[dict[str, typing.Any]] = None,
        before: typing.Optional[langchain_core.runnables.RunnableConfig] = None,
        limit: typing.Optional[int] = None,
    ) -> typing.AsyncIterator[langgraph.checkpoint.base.CheckpointTuple]:
        async for item in self.async_saver.alist(config=config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: langchain_core.runnables.RunnableConfig,
        checkpoint: langgraph.checkpoint.base.Checkpoint,
        metadata: langgraph.checkpoint.base.CheckpointMetadata,
        new_versions: langgraph.checkpoint.base.ChannelVersions,
    ) -> langchain_core.runnables.RunnableConfig:
        return await self.async_saver.aput(
            config=config, checkpoint=checkpoint, metadata=metadata, new_versions=new_versions
        )

    async def aput_writes(
        self,
        config: langchain_core.runnables.RunnableConfig,
        writes: typing.Sequence[tuple[str, typing.Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return await self.aput_writes(config=config, writes=writes, task_id=task_id)
