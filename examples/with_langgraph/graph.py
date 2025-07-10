import agentc_langgraph.graph
import dotenv
import langgraph.graph

from edge import out_front_desk_edge
from edge import out_route_finding_edge
from node import EndpointFindingAgent
from node import FrontDeskAgent
from node import RouteFindingAgent
from node import State

# Make sure you populate your .env file with the correct credentials!
dotenv.load_dotenv()


class FlightPlanner(agentc_langgraph.graph.GraphRunnable):
    @staticmethod
    def build_starting_state() -> State:
        return State(
            messages=[], endpoints=None, routes=None, needs_clarification=False, is_last_step=False, previous_node=None
        )

    def compile(self) -> langgraph.graph.StateGraph:
        # Build our nodes and agents.
        front_desk_agent = FrontDeskAgent(
            catalog=self.catalog,
            span=self.span,
        )
        endpoint_finding_agent = EndpointFindingAgent(
            catalog=self.catalog,
            span=self.span,
        )
        route_finding_agent = RouteFindingAgent(
            catalog=self.catalog,
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
            out_front_desk_edge,
            {
                "ENDPOINT_FINDING": "endpoint_finding_agent",
                "FRONT_DESK": "front_desk_agent",
                "END": langgraph.graph.END,
            },
        )
        workflow.add_edge("endpoint_finding_agent", "route_finding_agent")
        workflow.add_conditional_edges(
            "route_finding_agent",
            out_route_finding_edge,
            {"FRONT_DESK": "front_desk_agent", "ENDPOINT_FINDING": "endpoint_finding_agent"},
        )
        return workflow.compile()
