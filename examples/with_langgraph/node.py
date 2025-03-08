import agentc
import agentc_core.catalog.catalog
import agentc_core.prompt.models
import agentc_langchain
import langchain_core.language_models.chat_models
import langchain_core.messages
import langchain_core.runnables
import langchain_openai
import langgraph.graph
import langgraph.prebuilt
import typing


class State(typing.TypedDict):
    messages: list[langchain_core.messages.BaseMessage]
    endpoints: typing.Optional[dict]
    route: typing.Optional[dict]
    is_last_step: bool


class BaseAgent:
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, prompt_name: str, **kwargs):
        self.catalog: agentc.Catalog = catalog
        self.span: agentc.Span = span

        # Grab the prompt for our agent.
        self.prompt: agentc_core.catalog.catalog.Prompt = self.catalog.find("prompt", name=prompt_name)

        # All other keyword arguments are passed to our agent.
        self.agent_kwargs: dict = kwargs

    def _initialize_chat_model(self):
        # Initialize a chat model with OpenAI's GPT-4o model.
        self.chat_model: langchain_core.language_models.BaseChatModel = langchain_openai.chat_models.ChatOpenAI(
            model="gpt-4o", temperature=0, callbacks=[]
        )

    def _create_agent(self, span: agentc.Span):
        # A new agent object is created for each invocation of this node.
        self.chat_model.callbacks.append(agentc_langchain.chat.Callback(span=span))
        return langgraph.prebuilt.create_react_agent(
            model=self.chat_model,
            tools=self.prompt.tools,
            prompt=self.prompt.content["agent_instructions"],
            response_format=(self.prompt.content["output_format_instructions"], self.prompt.output),
            **self.agent_kwargs,
        )


class FrontDeskAgent(BaseAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        super().__init__(catalog=catalog, span=span, prompt_name="front_desk_node", **kwargs)
        self.introductory_message: str = "Please provide the source and destination airports.\n>"

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        if len(state["messages"]) == 0:
            # This is the first message in the conversation.
            response = input(self.introductory_message)
            state["messages"].append(langchain_core.messages.HumanMessage(content=response))
            return state

        else:
            # Display the last message in our conversation to our user.
            last_message = state["messages"][-1]
            response = input(last_message.content + "\n>")
            state["messages"].append(langchain_core.messages.HumanMessage(content=response))
            self._initialize_chat_model()

            # Below, we build a Span instance which will bind all logs to the name "front_desk_agent".
            # The "state" parameter is expected to be modified by the code in the WITH block.
            with self.span.new(name="front_desk_node", state=state) as span:
                agent = self._create_agent(span)

                # Give the working state to our agent.
                response = agent.invoke(input=state, config=config)

                # 'should_continue' and 'response' comes from the prompt's output format.
                # Note this is a direct mutation on the "state" given to the Span!
                structured_response = response["structured_response"]
                state["is_last_step"] = structured_response["should_continue"]
                state["messages"].append(langchain_core.messages.AIMessage(structured_response["response"]))

            return state


class EndpointFindingAgent(BaseAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        super().__init__(catalog=catalog, span=span, prompt_name="endpoint_finding_node", **kwargs)

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        self._initialize_chat_model()

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
        self._initialize_chat_model()

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
            state["route"] = structured_response

        return state
