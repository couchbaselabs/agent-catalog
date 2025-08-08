import langchain_core.runnables
import langchain_core.runnables.graph
import langgraph.graph
import langgraph.store.base
import typing

from agentc_core.activity import Span
from agentc_core.catalog import Catalog


class GraphRunnable[S](langchain_core.runnables.Runnable):
    """A helper class that wraps the "Runnable" interface with :py:class:`agentc.Span`.

    .. card:: Class Description

        This class is meant to handle some of the boilerplate around using :py:class:`agentc.Span` instances and
        LangGraph compiled graphs.
        Specifically, this class builds a new span on instantiation and wraps all ``Runnable`` methods in a Span's
        context manager.

        Below, we illustrate an example implementation of this class for a two-agent system.

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
                    return workflow.compile()

            if __name__ == '__main__':
                catalog = agentc.Catalog()
                state = MyResearchState(messages=[], is_last_step=False)
                MyResearcherApp(catalog=catalog).invoke(input=state)

        .. note::

            For more information around LangGraph's (LangChain's) ``Runnable`` interface, see LangChain's documentation
            `here <https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.base.Runnable.html>`__.

        .. tip::

            The example above does not use tools and prompts managed by Agent Catalog.
            See :py:class:`agentc_langgraph.agent.ReActAgent` for a helper class that handles some of the boilerplate
            around using LangGraph's prebuilt ReAct agent and Agent Catalog.
    """

    def __init__(self, *, catalog: Catalog, span: Span = None):
        self.catalog: Catalog = catalog
        if span is not None:
            self.span = span.new(name=self.__class__.__name__)
        else:
            self.span = catalog.Span(name=self.__class__.__name__)

    def compile(self) -> langgraph.graph.StateGraph:
        pass

    async def acompile(self) -> langgraph.graph.StateGraph:
        pass

    def get_graph(
        self, config: typing.Optional[langchain_core.runnables.RunnableConfig] = None
    ) -> langchain_core.runnables.graph.Graph:
        graph = self.compile()
        return graph.get_graph(config=config)

    def invoke(self, input: S, config: typing.Optional[langchain_core.runnables.RunnableConfig] = None, **kwargs) -> S:
        graph = self.compile()
        self.span.state = input
        with self.span:
            return graph.invoke(input=input, config=config, **kwargs)

    async def ainvoke(
        self, input: S, config: typing.Optional[langchain_core.runnables.RunnableConfig] = None, **kwargs
    ) -> S:
        graph = await self.acompile()
        self.span.state = input
        with self.span:
            return await graph.ainvoke(input=input, config=config, **kwargs)

    def stream(
        self, input: S, config: typing.Optional[langchain_core.runnables.RunnableConfig] = None, **kwargs
    ) -> typing.Iterator[S]:
        graph = self.compile()
        self.span.state = input
        with self.span:
            yield from graph.stream(input=input, config=config, **kwargs)

    async def astream(
        self, input: S, config: typing.Optional[langchain_core.runnables.RunnableConfig] = None, **kwargs
    ) -> typing.AsyncIterator[S]:
        graph = await self.acompile()
        self.span.state = input
        with self.span:
            async for event in graph.astream(input=input, config=config, **kwargs):
                yield event
