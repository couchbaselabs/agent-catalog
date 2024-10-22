import click.testing
import git
import os
import pathlib
import pytest
import re
import shutil
import uuid

from agentc_cli.main import click_main
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME


# ------------------ Helper functions ------------------
def assert_text_in_output(text, output):
    """Assert that text is present in output, with a descriptive message."""
    present = text in output
    assert present, f"Expected: '{text}' vs. actual : '{output}'"


def assert_output_matches(expected, output, catalog_name):
    """Assert that the output matches the expected output, with a descriptive message."""
    pattern = re.compile(expected)
    match = re.search(pattern, output)
    assert match, f"Expected output not found for {catalog_name}: '{expected}' vs. actual output: '{output}'"


# ------------------------------------------------------


def test_index(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        git.Repo.init(td)
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


@pytest.mark.smoke
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
    os.environ["CB_CONN_STRING"] = "couchbase://localhost"
    os.environ["CB_USERNAME"] = "Administrator"
    os.environ["CB_PASSWORD"] = "password"

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        git.Repo.init(td)
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        catalog_local_folder = pathlib.Path(__file__).parent / "resources" / "publish_catalog"
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
                    "Inserting metadata...\nSuccessfully inserted metadata.\nInserting catalog items...\n"
                    "Successfully inserted catalog items.\nCreating GSI indexes...\n"
                    "Successfully created GSI indexes.\nCreating vector index...\nSuccessfully created vector index."
                )
                print(f"Ran assertion for positive catalog: {catalog.name}")
                assert_output_matches(expected_output, output, catalog.name)


@pytest.mark.smoke
def test_find(tmp_path):
    """
    This test performs the following checks:
    1. command executes only for kind=tool assuming same behaviour for prompt
    2. command includes search for dirty versions of tool
    3. command tests the find capability and not recall/accuracy
    """
    runner = click.testing.CliRunner()
    # Set env variables
    os.environ["CB_CONN_STRING"] = "couchbase://localhost"
    os.environ["CB_USERNAME"] = "Administrator"
    os.environ["CB_PASSWORD"] = "password"

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        git.Repo.init(td)

        # Mock .agent-catalog dir in a temp file system
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        # Example tool-catalog.json
        catalog_local_folder = pathlib.Path(__file__).parent / "resources" / "find_catalog"
        # Copy file to temp dir under same name
        shutil.copy(catalog_local_folder / DEFAULT_TOOL_CATALOG_NAME, catalog_folder / DEFAULT_TOOL_CATALOG_NAME)

        # DB find
        output = runner.invoke(
            click_main,
            [
                "find",
                "--bucket",
                "travel-sample",
                "--kind",
                "tool",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
            ],
        ).stdout
        print("\nRan assertion for db find without limit clause (default 1 item is returned)")
        assert_text_in_output("1 result(s) returned from the catalog.", output)

        output = runner.invoke(
            click_main,
            [
                "find",
                "--bucket",
                "travel-sample",
                "--kind",
                "tool",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
                "--limit",
                "3",
            ],
        ).stdout
        print("Ran assertion for db find with limit=3")
        assert_text_in_output("3 result(s) returned from the catalog.", output)

        # Local find
        output = runner.invoke(
            click_main,
            [
                "find",
                "--kind",
                "tool",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
            ],
        ).stdout
        print("\nRan assertion for local find without limit clause (default 1 item is returned)")
        assert_text_in_output("1 result(s) returned from the catalog.", output)

        output = runner.invoke(
            click_main,
            [
                "find",
                "--kind",
                "tool",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
                "--limit",
                "3",
            ],
        ).stdout
        print("Ran assertion for local find with limit=3")
        assert_text_in_output("3 result(s) returned from the catalog.", output)


@pytest.mark.smoke
def test_status(tmp_path):
    runner = click.testing.CliRunner()
    print("\n\n")

    # Case 1 - catalog does not exist locally
    output = runner.invoke(click_main, ["status"]).stdout
    expected_response_tool = "local catalog of kind tool does not exist yet"
    expected_response_prompt = "local catalog of kind prompt does not exist yet"
    print("Ran assertion for local status when no catalog exists")
    assert_text_in_output(expected_response_tool, output)
    assert_text_in_output(expected_response_prompt, output)

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        git.Repo.init(td)

        # Mock .agent-catalog dir in a temp file system
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        # Example tool-catalog.json
        catalog_local_folder = pathlib.Path(__file__).parent / "resources" / "find_catalog"
        # Copy file to temp dir under same name
        shutil.copy(catalog_local_folder / DEFAULT_TOOL_CATALOG_NAME, catalog_folder / DEFAULT_TOOL_CATALOG_NAME)

        # Case 2 - tool catalog exists locally (testing for only one kind of catalog)
        output = runner.invoke(click_main, ["status", "--include-dirty", "--kind", "tool"]).stdout
        print("Ran assertion for local status when tool catalog exists")
        expected_response_local = "local catalog info:\n	path            : .agent-catalog/tool-catalog.json"
        assert_text_in_output(expected_response_local, output)

        # Case 3 - tool catalog exists in db (this test runs after publish test)
        # Set env variables
        os.environ["CB_CONN_STRING"] = "couchbase://localhost"
        os.environ["CB_USERNAME"] = "Administrator"
        os.environ["CB_PASSWORD"] = "password"

        output = runner.invoke(
            click_main, ["status", "--include-dirty", "--kind", "tool", "--status-db", "--bucket", "travel-sample"]
        ).stdout
        expected_response = "db catalog info"
        print("Ran assertion for db status when tool catalog exists")
        assert_text_in_output(expected_response, output)

        # Case 4 - compare the two catalogs
        output = runner.invoke(
            click_main, ["status", "--compare", "--kind", "tool", "--bucket", "travel-sample", "--include-dirty"]
        ).stdout
        expected_response_db_path = "path            : travel-sample.agent_catalog.tool"
        print("Ran assertion for compare status when tool catalog exists both locally and in db")
        assert_text_in_output(expected_response_db_path, output)
        assert_text_in_output(expected_response, output)
        assert_text_in_output(expected_response_local, output)


@pytest.mark.smoke
def test_clean(tmp_path):
    runner = click.testing.CliRunner()
    # Set env variables
    os.environ["CB_CONN_STRING"] = "couchbase://localhost"
    os.environ["CB_USERNAME"] = "Administrator"
    os.environ["CB_PASSWORD"] = "password"

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        git.Repo.init(td)
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        catalog_folder.mkdir()
        activity_folder.mkdir()

        # Local clean
        dummy_file_1 = catalog_folder / DEFAULT_PROMPT_CATALOG_NAME
        dummy_file_2 = catalog_folder / DEFAULT_TOOL_CATALOG_NAME
        with dummy_file_1.open("w") as fp:
            fp.write("dummy content")
        with dummy_file_2.open("w") as fp:
            fp.write("more dummy content")

        runner.invoke(click_main, ["clean", "-y"])

        print("\n\nRan assertion for local clean")
        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()

    # DB clean
    runner.invoke(click_main, ["clean", "-y", "-etype", "db", "--bucket", "travel-sample"])

    import json
    import requests

    # Get all scopes in bucket
    url = "http://localhost:8091/pools/default/buckets/travel-sample/scopes"
    auth = ("Administrator", "password")
    response = requests.request("GET", url, auth=auth, verify=False)
    scopes = json.loads(response.text)["scopes"]

    # Verify DEFAULT_CATALOG_SCOPE is deleted
    is_scope_present = False
    for scope in scopes:
        if scope["name"] == DEFAULT_CATALOG_SCOPE:
            is_scope_present = True
            break

    print("Ran assertion for db clean")
    assert not is_scope_present, f"Clean DB failed as scope {DEFAULT_CATALOG_SCOPE} is present in DB."


@pytest.mark.smoke
def test_status_after_clean(tmp_path):
    runner = click.testing.CliRunner()
    os.environ["CB_CONN_STRING"] = "couchbase://localhost"
    os.environ["CB_USERNAME"] = "Administrator"
    os.environ["CB_PASSWORD"] = "password"

    output = runner.invoke(
        click_main, ["status", "--include-dirty", "--kind", "tool", "--status-db", "--bucket", "travel-sample"]
    ).stdout
    expected_response_db = (
        "ERROR: db catalog of kind tool does not exist yet: please use the publish command by specifying the kind."
    )
    print("\n\nRan assertion for db status when tool catalog does not exist in db")
    assert_text_in_output(expected_response_db, output)
