import langgraph.graph
import node
import typing


def out_front_desk_edge(state: node.State) -> typing.Literal["endpoint_finding_agent", "__end__"]:
    if state["is_last_step"]:
        return langgraph.graph.END
    else:
        return "endpoint_finding_agent"


def out_route_finding_edge(state: node.State) -> typing.Literal["__end__", "endpoint_finding_agent"]:
    if state["routes"] or state["is_last_step"]:
        return langgraph.graph.END
    else:
        return "endpoint_finding_agent"
