import agentc
import dotenv
import langgraph.graph

from edge import out_talk_to_user_edge
from node import EndpointFindingAgent
from node import FrontDeskAgent
from node import RouteFindingAgent
from node import State

# Make sure you populate your .env file with the correct credentials!
dotenv.load_dotenv()


class Graph:
    def __init__(self, *args, catalog: agentc.Catalog, span: agentc.Span = None, **kwargs):
        self.span = catalog.Span(name="flight_planner") if span is None else span.new(name="flight_planner")

        # Build our nodes and agents.
        front_desk_agent = FrontDeskAgent(
            catalog=catalog,
            span=self.span,
        )
        endpoint_finding_agent = EndpointFindingAgent(
            catalog=catalog,
            span=self.span,
        )
        route_finding_agent = RouteFindingAgent(
            catalog=catalog,
            span=self.span,
        )

        # Create a workflow graph.
        workflow = langgraph.graph.StateGraph(State)
        workflow.add_node("front_desk_agent", front_desk_agent)
        workflow.add_node("endpoint_finding_agent", endpoint_finding_agent)
        workflow.add_node("route_finding_agent", route_finding_agent)
        workflow.set_entry_point("front_desk_agent")
        workflow.add_conditional_edges(
            "front_desk_agent",
            out_talk_to_user_edge,
            {"ENDPOINT_FINDING": "endpoint_finding_agent", "END": langgraph.graph.END},
        )
        workflow.add_edge("endpoint_finding_agent", "route_finding_agent")
        workflow.add_edge("route_finding_agent", "front_desk_agent")
        self.graph = workflow.compile(*args, **kwargs)

    def invoke(self, *args, **kwargs) -> State:
        state = State(messages=[], endpoints=None, routes=None, is_last_step=False)
        self.span.state = state
        with self.span:
            return self.graph.invoke(*args, input=state, **kwargs)


if __name__ == "__main__":
    import agentc

    # The Agent Catalog 'catalog' object serves versioned tools and prompts.
    # For a comprehensive list of what parameters can be set here, see the class documentation.
    # Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
    _catalog = agentc.Catalog()

    # Start our application.
    Graph(catalog=_catalog).invoke()
