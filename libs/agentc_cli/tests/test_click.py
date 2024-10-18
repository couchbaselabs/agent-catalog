import click.testing
import os
import pathlib
import pytest
import re
import shutil
import uuid

from agentc_cli.main import click_main
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME


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
        resources_folder = pathlib.Path(__file__).parent.parent / "agentc_core" / "tool" / "resources"
        for tool in resources_folder.rglob("*positive*"):
            shutil.copy(tool, tool_folder / (uuid.uuid4().hex + tool.suffix))

        # TODO (GLENN): Finish this test. This (unfortunately) requires a mock .git directory.
        # output = runner.invoke(click_main, ["index", "--include-dirty", str(tool_folder.absolute())])


def test_publish(tmp_path):
    """
    This test performs the following checks:
        1. command does not publish to kv when catalog is dirty
        2. command publishes to kv when catalog is clean
        3. command publishes catalogs when kind=tool/prompt
           but does not check for kind=all
        4. command ensures data is upserted and indexes created
    """
    runner = click.testing.CliRunner()
    # Set env variables
    os.environ["CB_CONN_STRING"] = "localhost"
    os.environ["CB_USERNAME"] = "Administrator"
    os.environ["CB_PASSWORD"] = "password"

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        catalog_local_folder = pathlib.Path(__file__).parent / "resources" / "catalogs"
        print("\n\n")

        for catalog in catalog_local_folder.rglob("*"):
            # Clean up file names (remove negative or positive from file name)
            new_catalog = str(catalog.name).replace("negative", "").replace("positive", "")
            new_catalog = new_catalog.replace("--", "-").replace("-.", ".").strip("-")
            # Copy file to temp dir under new name
            shutil.copy(catalog, catalog_folder / new_catalog)
            # Extract catalog kind
            kind = str(catalog.name).split("-")[0]

            # Execute the command
            output = runner.invoke(click_main, ["publish", "--bucket", "travel-sample", "--kind", kind]).stdout

            if "negative" in catalog.name:
                expected_output = "Cannot publish catalog to DB if dirty!\nPlease index catalog with a clean repo!"
                print(f"Ran assertion for negative catalog: {catalog.name}")
                assert_output_matches(expected_output, output, catalog.name)
            elif "positive" in catalog.name:
                expected_output = (
                    "Inserting metadata...\nSuccessfully inserted metadata.\nInserting catalog items..."
                    "\nSuccessfully inserted catalog items.\nCreating GSI indexes...\nSuccessfully created GSI indexes.\nCreating vector index...\nSuccessfully created vector index."
                )
                print(f"Ran assertion for positive catalog: {catalog.name}")
                assert_output_matches(expected_output, output, catalog.name)


def assert_output_matches(expected, output, catalog_name):
    """Assert that the output matches the expected output, with a descriptive message."""
    pattern = re.compile(expected)
    match = re.search(pattern, output)
    assert match, f"Expected output not found for {catalog_name}: '{expected}' vs. actual output: '{output}'"
