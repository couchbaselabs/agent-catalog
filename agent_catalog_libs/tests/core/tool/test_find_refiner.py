import datetime
import pathlib
import pytest
import uuid

from agent_catalog_libs.core.catalog import SearchResult
from agent_catalog_libs.core.provider.refiner import ClosestClusterRefiner
from agent_catalog_libs.core.record.descriptor import RecordDescriptor
from agent_catalog_libs.core.record.descriptor import RecordKind
from agent_catalog_libs.core.version.identifier import VersionDescriptor
from agent_catalog_libs.core.version.identifier import VersionSystem


def _generate_test_tools(deltas: list[int]) -> list[SearchResult]:
    tools_with_delta = list()
    for i, delta in enumerate(deltas):
        tools_with_delta.append(
            SearchResult(
                entry=RecordDescriptor(
                    record_kind=RecordKind.PythonFunction,
                    name="dummy tool #" + str(i),
                    description="a dummy tool #" + str(i),
                    source=pathlib.Path("."),
                    version=VersionDescriptor(
                        identifier=uuid.uuid4().hex,
                        version_system=VersionSystem.Raw,
                        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
                    ),
                ),
                delta=delta,
            )
        )
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
