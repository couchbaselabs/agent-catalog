import agentc
import agentc_langchain
import agentc_langgraph
import langchain_core
import langchain_core.language_models.chat_models
import langchain_core.messages
import langchain_core.runnables
import langchain_core.tools
import langchain_openai
import langgraph.graph
import langgraph.prebuilt
import typing


class State(typing.TypedDict):
    messages: list[langchain_core.messages.BaseMessage]
    is_last_step: bool
    needs_clarification: bool
    endpoints: typing.Optional[dict]
    routes: typing.Optional[list[dict]]


class BaseAgent:
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, prompt_name: str, **kwargs):
        self.catalog: agentc.Catalog = catalog
        self.span: agentc.Span = span

        # Grab the prompt for our agent.
        self.prompt: agentc.catalog.Prompt = self.catalog.find("prompt", name=prompt_name)

        # Initialize a chat model with OpenAI's GPT-4o model.
        self.chat_model: langchain_core.language_models.BaseChatModel = langchain_openai.chat_models.ChatOpenAI(
            model="gpt-4o", temperature=0, callbacks=[]
        )

        # All other keyword arguments are passed to our agent.
        self.agent_kwargs: dict = kwargs

    def _create_agent(self, span: agentc.Span):
        # LangChain agents expect LangChain tools, so we will convert the *pure Python functions* we get from Agent
        # Catalog into LangChain tools here.
        tools: list[langchain_core.tools.StructuredTool] = list()
        for tool in self.prompt.tools:
            tools.append(langchain_core.tools.StructuredTool.from_function(tool.func))

        # Add a callback to our chat model.
        callback = agentc_langchain.chat.Callback(span=span, tools=tools, output=self.prompt.output)
        self.chat_model.callbacks.append(callback)

        # Our callback only handles ChatCompletions, to record our tool calls we will provide a custom ToolNode.
        tool_node = agentc_langgraph.tools.ToolNode(span=span, tools=tools)

        # A new agent object is created for each invocation of this node.
        if isinstance(self.prompt.content["agent_instructions"], str):
            prompt_content = langchain_core.messages.SystemMessage(content=self.prompt.content["agent_instructions"])
        elif isinstance(self.prompt.content["agent_instructions"], list):
            prompt_parts: list[langchain_core.messages.BaseMessage] = list()
            for part in self.prompt.content["agent_instructions"]:
                prompt_parts.append(langchain_core.messages.SystemMessage(content=part))
            prompt_content = lambda _m: prompt_parts + _m["messages"]
        else:
            raise ValueError("Prompt content must be a string or a list of strings.")
        return langgraph.prebuilt.create_react_agent(
            model=self.chat_model,
            tools=tool_node,
            prompt=prompt_content,
            response_format=(self.prompt.content["output_format_instructions"], self.prompt.output),
            **self.agent_kwargs,
        )


class FrontDeskAgent(BaseAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        super().__init__(catalog=catalog, span=span, prompt_name="front_desk_node", **kwargs)
        self.introductory_message: str = "Please provide the source and destination airports."

    @staticmethod
    def _talk_to_user(span: agentc.Span, message: str, requires_response: bool = True):
        # We use "Assistant" to differentiate between the "internal" AI messages and what the user sees.
        span.log(agentc.span.AssistantContent(value=message))
        if requires_response:
            print("> Assistant: " + message)
            response = input("> User: ")
            span.log(agentc.span.UserContent(value=response))
            return response
        else:
            print("> Assistant: " + message)

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Below, we build a Span instance which will bind all logs to the name "front_desk_node".
        # The "state" parameter is expected to be modified by the code in the WITH block.
        with self.span.new(name="front_desk_node", state=state) as span:
            if len(state["messages"]) == 0:
                # This is the first message in the conversation.
                response = self._talk_to_user(span, self.introductory_message)
                state["messages"].append(langchain_core.messages.HumanMessage(content=response))
            else:
                # Display the last message in our conversation to our user.
                response = self._talk_to_user(span, state["messages"][-1].content)
                state["messages"].append(langchain_core.messages.HumanMessage(content=response))

            # Give the working state to our "agent" (in this case, just an LLM call).
            callback = agentc_langchain.chat.Callback(span=span, output=self.prompt.output)
            self.chat_model.callbacks.append(callback)
            chat_model = self.chat_model.with_structured_output(self.prompt.output)
            structured_response = chat_model.invoke(state["messages"], config=config)

            # 'is_last_step' and 'response' comes from the prompt's output format.
            # Note this is a direct mutation on the "state" given to the Span!
            state["messages"].append(langchain_core.messages.AIMessage(structured_response["response"]))
            state["is_last_step"] = structured_response["is_last_step"]
            state["needs_clarification"] = structured_response["needs_clarification"]
            if state["is_last_step"]:
                self._talk_to_user(span, structured_response["response"], requires_response=False)
            return state


class EndpointFindingAgent(BaseAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        super().__init__(catalog=catalog, span=span, prompt_name="endpoint_finding_node", **kwargs)

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Below, we build a Span instance which will bind all logs to the name "endpoint_finding_node".
        # The "state" parameter is expected to be modified by the code in the WITH block.
        with self.span.new(name="endpoint_finding_node", state=state) as span:
            agent = self._create_agent(span)

            # Give the working state to our agent.
            response = agent.invoke(input=state, config=config)

            # 'source' and 'dest' comes from the prompt's output format.
            # Note this is a direct mutation on the "state" given to the Span!
            structured_response = response["structured_response"]
            state["endpoints"] = {"source": structured_response["source"], "destination": structured_response["dest"]}
            state["messages"].append(response["messages"][-1])
            return state


class RouteFindingAgent(BaseAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        super().__init__(catalog=catalog, span=span, prompt_name="route_finding_node", **kwargs)

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Below, we build a Span instance which will bind all logs to the name "route_finding_node".
        # The "state" parameter is expected to be modified by the code in the WITH block.
        with self.span.new(name="route_finding_node", state=state) as span:
            agent = self._create_agent(span)

            # Give the working state to our agent.
            response = agent.invoke(input=state, config=config)

            # We will only attach the last message to our state.
            # Note this is a direct mutation on the "state" given to the Span!
            structured_response = response["structured_response"]
            state["messages"].append(response["messages"][-1])
            state["routes"] = structured_response["routes"]
            state["is_last_step"] = structured_response["is_last_step"] is True
            return state
