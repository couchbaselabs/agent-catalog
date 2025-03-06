import node
import typing


def out_talk_to_user_edge(state: node.State) -> typing.Literal["ENDPOINT_FINDING", "END"]:
    if state["is_last_step"]:
        return "END"
    else:
        return "ENDPOINT_FINDING"
