import os
import pathlib
import pytest

from agentc_core.catalog.directory import scan_directory
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.indexer.indexer import AllIndexers


@pytest.mark.smoke
def test_scan_dir_tools():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "scan_files")
    source_globs = [i.glob_pattern for i in AllIndexers if all(k.is_tool() for k in i.kind)]
    output = []
    output += scan_directory(root_dir, "tools", source_globs, opts=DEFAULT_SCAN_DIRECTORY_OPTS)

    assert (
        pathlib.PosixPath(os.path.join(root_dir, "tools", "tool3.sqlpp")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "tools", "tool4.py")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "tools", "tool2.sqlpp")) not in output
        and pathlib.PosixPath(os.path.join(root_dir, "tool1.py")) not in output
    )


@pytest.mark.smoke
def test_scan_dir_prompts():
    root_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "scan_files")
    source_globs = [i.glob_pattern for i in AllIndexers if all(k.is_prompt() for k in i.kind)]
    output = []
    output += scan_directory(root_dir, "prompts", source_globs, opts=DEFAULT_SCAN_DIRECTORY_OPTS)

    assert (
        pathlib.PosixPath(os.path.join(root_dir, "prompts", "prompt1.jinja")) in output
        and pathlib.PosixPath(os.path.join(root_dir, "prompts", "prompt2.prompt")) not in output
    )
