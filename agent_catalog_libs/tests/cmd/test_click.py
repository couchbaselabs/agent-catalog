import click.testing
import pathlib
import pytest
import shutil
import uuid

from agent_catalog_libs.cmd.defaults import DEFAULT_ACTIVITY_FOLDER
from agent_catalog_libs.cmd.defaults import DEFAULT_CATALOG_FOLDER
from agent_catalog_libs.cmd.defaults import DEFAULT_PROMPT_CATALOG_NAME
from agent_catalog_libs.cmd.defaults import DEFAULT_TOOL_CATALOG_NAME
from agent_catalog_libs.cmd.main import click_main


@pytest.mark.smoke
def test_clean(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        catalog_folder.mkdir()
        activity_folder.mkdir()

        dummy_file_1 = catalog_folder / DEFAULT_PROMPT_CATALOG_NAME
        dummy_file_2 = catalog_folder / DEFAULT_TOOL_CATALOG_NAME
        with dummy_file_1.open("w") as fp:
            fp.write("dummy content")
        with dummy_file_2.open("w") as fp:
            fp.write("more dummy content")
        # TODO: might need to test for clean db as well
        runner.invoke(click_main, ["clean", "-y"])

        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()


def test_index(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        tool_folder = pathlib.Path(td) / "tools"
        catalog_folder.mkdir()
        activity_folder.mkdir()
        tool_folder.mkdir()

        # Copy all positive tool into our tools.
        resources_folder = pathlib.Path(__file__).parent.parent / "core" / "tool" / "resources"
        for tool in resources_folder.rglob("*positive*"):
            shutil.copy(tool, tool_folder / (uuid.uuid4().hex + tool.suffix))

        # TODO (GLENN): Finish this test. This (unfortunately) requires a mock .git directory.
        # output = runner.invoke(click_main, ["index", "--include-dirty", str(tool_folder.absolute())])
