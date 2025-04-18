import abc
import agentc_core.activity.models.content
import langchain_core
import langchain_core.language_models.chat_models
import langchain_core.messages
import langchain_core.runnables
import langchain_core.tools
import langgraph.prebuilt
import langgraph.types
import typing

from agentc import Catalog
from agentc import Span
from agentc.catalog import Prompt
from agentc_langchain.chat import Callback
from agentc_langgraph.tool import ToolNode


class State(typing.TypedDict):
    """An (optional) state class for use with Agent Catalog's LangGraph helper classes.

    .. card:: Class Description

        The primary use for this class to help :py:class:`agentc_langgraph.agent.ReActAgent` instances build
        :py:class:`agentc.span.EdgeContent` logs.
        This class is essentially identical to the default state schema for LangGraph (i.e.,
        ``messages`` and ``is_last_step``) *but* with the inclusion of a new ``previous_node`` field.

    """

    messages: list[langchain_core.messages.BaseMessage]
    is_last_step: bool
    previous_node: typing.Optional[list[str]]


class ReActAgent[S: State]:
    """A helper ReAct agent base class that integrates with Agent Catalog.

    .. card:: Class Description

        This class is meant to handle some of the boilerplate around using Agent Catalog with LangGraph's prebuilt
        ReAct agent.
        More specifically, this class performs the following:

        1. Fetches the prompt given the name (``prompt_name``) in the constructor and supplies the prompt and tools
           attached to the prompt to the ReAct agent constructor.
        2. Attaches a :py:class:`agentc_langchain.chat.Callback` to the given ``chat_model`` to record all chat-model
           related activity (i.e., chat completions and tool calls).
        3. Wraps tools (if present in the prompt) in a :py:class:`agentc_langgraph.tool.ToolNode` instance to record
           the results of tool calls.
        4. Wraps the invocation of this agent in a :py:class:`agentc.Span` context manager.

        Below, we illustrate an example Agent Catalog prompt and an implementation of this class for our prompt.
        First, our prompt:

        .. code-block:: yaml

            record_kind: prompt
            name: endpoint_finding_node
            description: All inputs required to assemble the endpoint finding agent.

            output:
              title: Endpoints
              description: The source and destination airports for a flight / route.
              type: object
              properties:
                source:
                  type: string
                  description: "The IATA code for the source airport."
                dest:
                  type: string
                  description: "The IATA code for the destination airport."
              required: [source, dest]

            content:
              agent_instructions: >
                Your task is to find the source and destination airports for a flight.
                The user will provide you with the source and destination cities.
                You need to find the IATA codes for the source and destination airports.
                Another agent will use these IATA codes to find a route between the two airports.
                If a route cannot be found, suggest alternate airports (preferring airports that are more likely to have
                routes between them).

              output_format_instructions: >
                Ensure that each IATA code is a string and is capitalized.

        Next, the usage of this prompt in an implementation of this class:

        .. code-block:: python

            import langchain_core.messages
            import agentc_langgraph.agent
            import agentc
            import typing

            class State(agentc_langgraph.state):
                endpoints: typing.Optional[dict]

            class EndpointFindingAgent(agentc_langgraph.agent.ReActAgent):
                def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
                    chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)
                    super().__init__(
                        chat_model=chat_model,
                        catalog=catalog,
                        span=span,
                        prompt_name="endpoint_finding_node",
                         **kwargs
                    )

                def _invoke(self, span: agentc.Span, state: State, config) -> State:
                    # Give the working state to our agent.
                    agent = self.create_react_agent(span)
                    response = agent.invoke(input=state, config=config)

                    # 'source' and 'dest' comes from the prompt's output format.
                    # Note this is a direct mutation on the "state" given to the Span!
                    structured_response = response["structured_response"]
                    state["endpoints"] = {"source": structured_response["source"], "destination": structured_response["dest"]}
                    state["messages"].append(response["messages"][-1])
                    return state

            if __name__ == '__main__':
                catalog = agentc.Catalog()
                span = catalog.Span(name="root_span")
                my_agent = EndpointFindingAgent(catalog=catalog, span=span)

    .. note::

        For all constructor parameters, see the documentation for :py:class:`langgraph.prebuilt.create_react_agent`
        `here <https://langchain-ai.github.io/langgraph/reference/prebuilt/#langgraph.prebuilt.chat_agent_executor.create_react_agent>`__.

    """

    def __init__(
        self,
        chat_model: langchain_core.language_models.BaseChatModel,
        catalog: Catalog,
        span: Span,
        prompt_name: str = None,
    ):
        self.catalog: Catalog = catalog
        self.span: Span = span
        self.chat_model: langchain_core.language_models.BaseChatModel = chat_model
        if self.chat_model.callbacks is None:
            self.chat_model.callbacks = []

        self.tools: list[langchain_core.tools.Tool] = list()
        self.prompt_content = None
        self.output: dict = None

        # Grab the prompt for our agent.
        self.prompt: Prompt = None
        self.prompt_name: str = prompt_name
        if prompt_name is not None:
            self.prompt: Prompt = self.catalog.find("prompt", name=prompt_name)

            # LangChain agents expect LangChain tools, so we will convert the *pure Python functions* we get from Agent
            # Catalog into LangChain tools here.
            for tool in self.prompt.tools:
                self.tools.append(langchain_core.tools.StructuredTool.from_function(tool.func))

            # Grab our prompt content.
            if isinstance(self.prompt.content, str):
                self.prompt_content = langchain_core.messages.SystemMessage(content=self.prompt.content)

            elif (
                isinstance(self.prompt.content, dict)
                and "agent_instructions" in self.prompt.content
                and isinstance(self.prompt.content["agent_instructions"], str)
            ):
                self.prompt_content = langchain_core.messages.SystemMessage(
                    content=self.prompt.content["agent_instructions"]
                )
            elif (
                isinstance(self.prompt.content, dict)
                and "agent_instructions" in self.prompt.content
                and isinstance(self.prompt.content["agent_instructions"], list)
            ):
                prompt_parts: list[langchain_core.messages.BaseMessage] = list()
                for part in self.prompt.content["agent_instructions"]:
                    prompt_parts.append(langchain_core.messages.SystemMessage(content=part))
                self.prompt_content = lambda _m: prompt_parts + _m["messages"]
            else:
                raise ValueError("""
                    Prompt content must be either a string, **or** a dictionary with 'agent_instructions'.
                    If 'agent_instructions' is specified, this field must be a string **or** a list of strings.
                """)

            # Grab our response format.
            if isinstance(self.prompt.content, str):
                self.output = self.prompt.output
            elif isinstance(self.prompt.content, dict) and "output_format_instructions" in self.prompt.content:
                self.output = (self.prompt.content["output_format_instructions"], self.prompt.output)
            else:
                self.output = self.prompt.output

    def create_react_agent(self, span: Span, tools: typing.Sequence[langchain_core.tools.Tool] = None, **kwargs):
        """A wrapper around LangGraph's create_react_agent for use with Agent Catalog.

        :param span: The :py:class:`agentc.Span` instance to use for all logs generated by this agent.
        :param tools: An optional list of LangChain tools to provide to create the agent with.

        .. note::

            For all possible arguments that can be used with this method, see the documentation for
            :py:class:`langgraph.prebuilt.chat_agent_executor.create_react_agent` `here <https://langchain-ai.github.io/langgraph/reference/prebuilt/#langgraph.prebuilt.chat_agent_executor.create_react_agent>`__.
        """
        agent_tools = list(self.tools)
        if tools is not None:
            agent_tools.append(tools)

        # Add a callback to our chat model.
        callback = Callback(span=span, tools=agent_tools, output=self.output)
        self.chat_model.callbacks.append(callback)

        # Our callback only handles ChatCompletions, to record our tool calls we will provide a custom ToolNode.
        tool_node = ToolNode(span=span, tools=agent_tools)

        # A new agent object is created for each invocation of this node.
        agent_kwargs = kwargs.copy()
        if self.prompt_content is not None:
            agent_kwargs["prompt"] = self.prompt_content
        if self.output is not None:
            agent_kwargs["response_format"] = self.output
        return langgraph.prebuilt.create_react_agent(
            model=self.chat_model,
            tools=tool_node,
            **agent_kwargs,
        )

    @abc.abstractmethod
    def _invoke(
        self, span: Span, state: S, config: langchain_core.runnables.RunnableConfig
    ) -> S | langgraph.types.Command:
        pass

    def __call__(self, state: S, config: langchain_core.runnables.RunnableConfig) -> S | langgraph.types.Command:
        node_name = self.__class__.__name__

        # Below, we build a Span instance which will bind all logs to our class name.
        # The "state" parameter is expected to be modified by the code in the WITH block.
        with self.span.new(name=node_name, state=state, agent_name=node_name) as span:
            if state["previous_node"] is not None:
                self.span.log(
                    content=agentc_core.activity.models.content.EdgeContent(
                        source=state["previous_node"], dest=span.identifier.name, payload=state
                    )
                )
            result = self._invoke(span, state, config)
            if isinstance(result, dict):
                state["previous_node"] = span.identifier.name
                return result

            elif isinstance(result, langgraph.types.Command):
                result.update["previous_node"] = span.identifier.name
                state.update(result.update)
                return result

            else:
                raise RuntimeError("_invoke() must return an instance of State OR a LangGraph Command.")
