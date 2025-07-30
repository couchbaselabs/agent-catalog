import agentc
import agentc_langgraph.agent
import langchain_core.messages
import langchain_core.runnables
import langchain_openai.chat_models
import typing


class State(agentc_langgraph.agent.State):
    endpoints: typing.Optional[dict]
    routes: typing.Optional[list[dict]]


class FrontDeskAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o-mini", temperature=0)
        super().__init__(chat_model=chat_model, catalog=catalog, span=span, prompt_name="front_desk_node")

    async def _ainvoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        if state["messages"][-1].type == "human":
            span.log(agentc.span.UserContent(value=state["messages"][-1].content))

        # Give the working state to our agent.
        agent = self.create_react_agent(span)
        response = await agent.ainvoke(input=state, config=config)

        # 'are_endpoints_given' and 'response' comes from the prompt's output format.
        # Note this is a direct mutation on the "state" given to the Span!
        structured_response = response["structured_response"]
        state["messages"].append(langchain_core.messages.AIMessage(structured_response["response"]))
        state["is_last_step"] = not structured_response["are_endpoints_given"]
        if state["is_last_step"]:
            span.log(agentc.span.AssistantContent(value=structured_response["response"]))
        return state


class EndpointFindingAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o-mini", temperature=0)
        super().__init__(chat_model=chat_model, catalog=catalog, span=span, prompt_name="endpoint_finding_node")

    async def _ainvoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Give the working state to our agent.
        agent = self.create_react_agent(span)
        response = await agent.ainvoke(input=state, config=config)

        # 'source' and 'dest' comes from the prompt's output format.
        # Note this is a direct mutation on the "state" given to the Span!
        structured_response = response["structured_response"]
        state["endpoints"] = {"source": structured_response["source"], "destination": structured_response["dest"]}
        state["messages"].append(response["messages"][-1])
        return state


class RouteFindingAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o-mini", temperature=0)
        super().__init__(chat_model=chat_model, catalog=catalog, span=span, prompt_name="route_finding_node")

    async def _ainvoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Give the working state to our agent.
        agent = self.create_react_agent(span)
        response = await agent.ainvoke(input=state, config=config)

        # We will only attach the last message to our state.
        # Note this is a direct mutation on the "state" given to the Span!
        structured_response = response["structured_response"]
        state["messages"].append(response["messages"][-1])
        state["routes"] = structured_response["routes"]
        state["is_last_step"] = structured_response["is_last_step"] is True
        return state
