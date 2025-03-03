import agentc
import agentc_core.catalog.catalog
import agentc_core.prompt.models
import agentc_langchain
import datetime
import langchain_core.language_models.chat_models
import langchain_core.messages
import langchain_core.runnables
import langgraph.graph
import langgraph.prebuilt
import pydantic
import typing


class Endpoints(pydantic.BaseModel):
    source: str
    dest: str
    departure_time: datetime.date


class Route(pydantic.BaseModel):
    flights: list[Endpoints]


class State(typing.TypedDict):
    messages: list[langchain_core.messages.BaseMessage]
    endpoints: typing.Optional[Endpoints]
    route: typing.Optional[Route]
    is_last_step: bool


class TalkToUserNode:
    def __init__(self):
        # Note: this is a prompt for our user, not for any of our agents.
        self.introductory_message: str = "Please provide the source and destination airports."

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        if len(state["messages"]) == 0:
            # This is the first message in the conversation.
            response = input(self.introductory_message)
            state["messages"].append(langchain_core.messages.HumanMessage(content=response))
            return state

        else:
            # Display the last message in our conversation to our user.
            last_message = state["messages"][-1]
            response = input(last_message.content)
            state["messages"].append(langchain_core.messages.HumanMessage(content=response))
            return state


class EndpointFindingAgent:
    def __init__(
        self,
        catalog: agentc.Catalog,
        scope: agentc.Span,
        chat_model: langchain_core.language_models.BaseChatModel,
        **kwargs,
    ):
        self.catalog: agentc.Catalog = catalog
        self.scope: agentc.Span = scope

        # Grab the prompt for our endpoint-finding node.
        self.prompt: agentc_core.catalog.catalog.Prompt = self.catalog.get("prompt", name="endpoint_finding_node")
        self.chat_model: langchain_core.language_models.BaseChatModel = chat_model

        # All other keyword arguments are passed to our agent.
        self.agent_kwargs: dict = kwargs

    def __call__(self, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Below, we build a Scope instance which will bind all logs to the name "endpoint_finding_node".
        # The "state" parameter is expected to be modified by the code in the WITH block.
        with self.scope.new(name="endpoint_finding_node", state=state) as scope:
            # A new agent object is created for each invocation of this node.
            agent: langgraph.graph.graph.CompiledGraph = langgraph.prebuilt.create_react_agent(
                model=agentc_langchain.audit(self.chat_model, scope),
                tools=self.prompt.tools,
                prompt=self.prompt.content["agent_instructions"],
                response_format=(self.prompt.content["output_format_instructions"], self.prompt.output),
                **self.agent_kwargs,
            )

            # Give the working state to our agent.
            response = agent.invoke(input=state, config=config)

            # We will only attach the last message to our state.
            # Note this is a direct mutation on the "state" given to the Scope!
            state["messages"].append(response["messages"][-1])

        return state
