import langgraph.graph
import node
import typing


def out_front_desk_edge(state: node.State) -> typing.Literal["endpoint_finding_agent", "front_desk_agent", "__end__"]:
    if state["is_last_step"]:
        return langgraph.graph.END
    elif state["needs_clarification"]:
        return "front_desk_agent"
    else:
        return "endpoint_finding_agent"


def out_route_finding_edge(state: node.State) -> typing.Literal["front_desk_agent", "endpoint_finding_agent"]:
    if state["routes"] or state["is_last_step"]:
        return "front_desk_agent"
    else:
        return "endpoint_finding_agent"
