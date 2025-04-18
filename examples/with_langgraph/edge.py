import node
import typing


def out_front_desk_edge(state: node.State) -> typing.Literal["ENDPOINT_FINDING", "FRONT_DESK", "END"]:
    if state["is_last_step"]:
        return "END"
    elif state["needs_clarification"]:
        return "FRONT_DESK"
    else:
        return "ENDPOINT_FINDING"


def out_route_finding_edge(state: node.State) -> typing.Literal["FRONT_DESK", "ENDPOINT_FINDING"]:
    if state["routes"] or state["is_last_step"]:
        return "FRONT_DESK"
    else:
        return "ENDPOINT_FINDING"
