import os
import pathlib
import pytest

from agentc_core.catalog.directory import scan_directory
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.indexer.indexer import AllIndexers
from agentc_core.record.descriptor import RecordKind


@pytest.mark.smoke
def test_scan_dir_tools():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "scan_files")
    source_globs = [i.glob_pattern for i in AllIndexers if any(k != RecordKind.ModelInput for k in i.kind)]
    output = []
    output += scan_directory(root_dir, "tools", source_globs, opts=DEFAULT_SCAN_DIRECTORY_OPTS)

    assert (
        pathlib.PosixPath(os.path.join(root_dir, "tools", "tool3.sqlpp")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "tools", "tool4.py")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "tools", "tool2.sqlpp")) not in output
        and pathlib.PosixPath(os.path.join(root_dir, "tool1.py")) not in output
    )


@pytest.mark.smoke
def test_scan_dir_inputs():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "scan_files")
    source_globs = [i.glob_pattern for i in AllIndexers if any(k == RecordKind.ModelInput for k in i.kind)]
    output = []
    output += scan_directory(root_dir, "inputs", source_globs, opts=DEFAULT_SCAN_DIRECTORY_OPTS)

    assert (
        pathlib.PosixPath(os.path.join(root_dir, "inputs", "prompt1.yaml")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "inputs", "prompt2.yaml")) not in output
    )
