import uuid
import click.testing
import pytest
import shutil
import pathlib

from rosetta.cmd.main import click_main
from rosetta.cmd.defaults import (
    DEFAULT_CATALOG_FOLDER,
    DEFAULT_ACTIVITY_FOLDER,
    DEFAULT_TOOL_CATALOG_NAME,
    DEFAULT_PROMPT_CATALOG_NAME
)


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
        with dummy_file_1.open('w') as fp:
            fp.write('dummy content')
        with dummy_file_2.open('w') as fp:
            fp.write('more dummy content')
        runner.invoke(click_main, ['clean'])

        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()


def test_index(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        tool_folder = pathlib.Path(td) / 'tools'
        catalog_folder.mkdir()
        activity_folder.mkdir()
        tool_folder.mkdir()

        # Copy all positive tool into our tools.
        resources_folder = pathlib.Path(__file__).parent.parent / 'core' / 'tool' / 'resources'
        for tool in resources_folder.rglob('*positive*'):
            shutil.copy(tool, tool_folder / (uuid.uuid4().hex + tool.suffix))

        # TODO (GLENN): Finish this test. This (unfortunately) requires a mock .git directory.
        output = runner.invoke(click_main, ['index', '--include-dirty', str(tool_folder.absolute())])
