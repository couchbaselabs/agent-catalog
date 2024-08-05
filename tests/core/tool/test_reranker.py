import pytest
import langchain_core.tools

from rosetta.core.tool.reranker import (
    ClosestClusterReranker,
    ToolWithDelta
)


def _generate_test_tools(deltas: list[int]) -> list[ToolWithDelta]:
    tools_with_delta = list()
    for i, delta in enumerate(deltas):
        def dummy_tool(j: int) -> int:
            """ dummy tool """
            return i

        new_tool = langchain_core.tools.StructuredTool.from_function(
            func=dummy_tool,
            name=f'Tool {i}'
        )
        tools_with_delta.append(ToolWithDelta(
            tool=new_tool,
            delta=delta
        ))
    return tools_with_delta


@pytest.mark.smoke
def test_closest_cluster_reranker():
    reranker = ClosestClusterReranker()

    same_tools = _generate_test_tools([0.1 for _ in range(0, 10)])
    assert same_tools == reranker(same_tools)

    one_tool_cluster = _generate_test_tools([0.999, 0.6, 0.6, 0.5, 0.3, -0.3])
    assert [one_tool_cluster[0]] == reranker(one_tool_cluster)

    two_tool_cluster = _generate_test_tools([0.9990, 0.9989, 0.6, 0.6, 0.5, 0.3, -0.3])
    assert two_tool_cluster[0:2] == reranker(two_tool_cluster)


