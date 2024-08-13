import pathlib
import uuid
import pytest

from rosetta.core.catalog.catalog_base import SearchResult
from rosetta.core.record.descriptor import (
    RecordDescriptor, RecordKind
)
from rosetta.core.provider.refiner import (
    ClosestClusterRefiner
)


def _generate_test_tools(deltas: list[int]) -> list[SearchResult]:
    tools_with_delta = list()
    for i, delta in enumerate(deltas):
        tools_with_delta.append(SearchResult(
            entry=RecordDescriptor(
                identifier=str(i),
                record_kind=RecordKind.PythonFunction,
                name='dummy tool #' + str(i),
                description='a dummy tool #' + str(i),
                source=pathlib.Path('.'),
                repo_commit_id=uuid.uuid4().hex,
            ),
            delta=delta
        ))
    return tools_with_delta


@pytest.mark.smoke
def test_closest_cluster_refiner():
    refiner = ClosestClusterRefiner()

    same_tools = _generate_test_tools([0.1 for _ in range(0, 10)])
    assert same_tools == refiner(same_tools)

    one_tool_cluster = _generate_test_tools([0.999, 0.6, 0.6, 0.5, 0.3, -0.3])
    assert [one_tool_cluster[0]] == refiner(one_tool_cluster)

    two_tool_cluster = _generate_test_tools([0.9990, 0.9989, 0.6, 0.6, 0.5, 0.3, -0.3])
    assert two_tool_cluster[0:2] == refiner(two_tool_cluster)
