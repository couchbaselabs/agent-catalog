import agentc
import dotenv
import langchain_openai
import langgraph.graph
import uuid

from edge import out_talk_to_user_edge
from node import EndpointFindingAgent
from node import State
from node import TalkToUserNode

# Make sure you populate your .env file with the correct credentials!
dotenv.load_dotenv()


class Graph:
    def __init__(self, *args, catalog: agentc.Catalog, scope: agentc.Span, **kwargs):
        # Initialize a chat model with OpenAI's GPT-4o model.
        chat_model = langchain_openai.chat_models.ChatOpenAI(model_name="gpt-4o", temperature=0)

        # The parent scope is used to bind all logs to the name "flight_planner".
        scope = scope.new(name="flight_planner")

        # Build our nodes and agents.
        talk_to_user_node = TalkToUserNode()
        endpoint_finding_agent = EndpointFindingAgent(
            catalog=catalog,
            scope=scope,
            chat_model=chat_model,
            session_id=_session_id,
        )

        # Create a workflow graph.
        workflow = langgraph.graph.StateGraph(State)
        workflow.add_node("talk_to_user_node", talk_to_user_node)
        workflow.add_node("endpoint_finding_agent", endpoint_finding_agent)
        workflow.set_entry_point("talk_to_user_node")
        workflow.add_conditional_edges(
            "talk_to_user_node",
            out_talk_to_user_edge,
            {"ENDPOINT_FINDING": "endpoint_finding_agent", "END": langgraph.graph.END},
        )
        workflow.add_edge("endpoint_finding_agent", "talk_to_user_node")
        self.graph = workflow.compile(*args, **kwargs)

    def invoke(self, *args, **kwargs) -> State:
        return self.graph.invoke(*args, **kwargs)


if __name__ == "__main__":
    import agentc

    # The Agent Catalog 'catalog' object serves versioned tools and prompts.
    # For a comprehensive list of what parameters can be set here, see the class documentation.
    # Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
    _catalog = agentc.Catalog()

    # A session ID is used to identify a specific conversation thread.
    # For this application, we will generate a new session ID for each conversation.
    # This session ID serves as the top-level scope for all logs here.
    _session_id = uuid.uuid4().hex

    # Start our application.
    _scope = _catalog.Span(name=_session_id)
    Graph(catalog=_catalog, scope=_scope).invoke(input=dict())
