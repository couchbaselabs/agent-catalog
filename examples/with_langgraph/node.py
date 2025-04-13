import agentc
import agentc_langchain
import agentc_langgraph.agent
import langchain_core.messages
import langchain_core.runnables
import langchain_openai.chat_models
import typing


class State(agentc_langgraph.agent.State):
    needs_clarification: bool
    endpoints: typing.Optional[dict]
    routes: typing.Optional[list[dict]]


class FrontDeskAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)
        super().__init__(chat_model=chat_model, catalog=catalog, span=span, prompt_name="front_desk_node", **kwargs)
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

    def _invoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
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


class EndpointFindingAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)
        super().__init__(
            chat_model=chat_model, catalog=catalog, span=span, prompt_name="endpoint_finding_node", **kwargs
        )

    def _invoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Give the working state to our agent.
        agent = self.create_react_agent(span)
        response = agent.invoke(input=state, config=config)

        # 'source' and 'dest' comes from the prompt's output format.
        # Note this is a direct mutation on the "state" given to the Span!
        structured_response = response["structured_response"]
        state["endpoints"] = {"source": structured_response["source"], "destination": structured_response["dest"]}
        state["messages"].append(response["messages"][-1])
        return state


class RouteFindingAgent(agentc_langgraph.agent.ReActAgent):
    def __init__(self, catalog: agentc.Catalog, span: agentc.Span, **kwargs):
        chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)
        super().__init__(chat_model=chat_model, catalog=catalog, span=span, prompt_name="route_finding_node", **kwargs)

    def _invoke(self, span: agentc.Span, state: State, config: langchain_core.runnables.RunnableConfig) -> State:
        # Give the working state to our agent.
        agent = self.create_react_agent(span)
        response = agent.invoke(input=state, config=config)

        # We will only attach the last message to our state.
        # Note this is a direct mutation on the "state" given to the Span!
        structured_response = response["structured_response"]
        state["messages"].append(response["messages"][-1])
        state["routes"] = structured_response["routes"]
        state["is_last_step"] = structured_response["is_last_step"] is True
        return state
