import click.testing
import couchbase.auth
import couchbase.cluster
import couchbase.options
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
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import DEFAULT_COUCHBASE_CONN_STRING
from agentc_testing.server import DEFAULT_COUCHBASE_PASSWORD
from agentc_testing.server import DEFAULT_COUCHBASE_USERNAME
from agentc_testing.server import isolated_server_factory
from unittest.mock import patch

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory


@pytest.mark.smoke
def test_index(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        repo = git.Repo.init(td)
        repo.index.commit("Initial commit")
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        tool_folder = pathlib.Path(td) / "tools"
        catalog_folder.mkdir()
        activity_folder.mkdir()
        tool_folder.mkdir()

        # Copy all positive tool into our tools.
        resources_folder = pathlib.Path(__file__).parent.parent.parent / "agentc_core" / "tests" / "tool" / "resources"
        for tool in resources_folder.rglob("*positive*"):
            if tool.suffix == ".pyc":
                continue
            pathlib.Path(tool_folder / tool.parent.name).mkdir(exist_ok=True)
            shutil.copy(tool, tool_folder / tool.parent.name / (uuid.uuid4().hex + tool.suffix))
        shutil.copy(resources_folder / "_good_spec.json", tool_folder / "_good_spec.json")
        runner.invoke(click_main, ["init", "local", "model"])
        invocation = runner.invoke(click_main, ["index", str(tool_folder.absolute()), "--no-prompts"])

        # We should see 11 files scanned and 12 tools indexed.
        output = invocation.output
        print(output)
        assert "Crawling" in output
        assert "Generating embeddings" in output
        assert "Catalog successfully indexed" in output
        assert "0/11" in output
        assert "0/12" in output


# Small helper function to publish to a Couchbase catalog.
def publish_catalog(runner, input_catalog: pathlib.Path, output_catalog: pathlib.Path):
    os.environ["AGENT_CATALOG_MAX_SOURCE_PARTITION"] = "1"
    os.environ["AGENT_CATALOG_INDEX_PARTITION"] = "1"

    # Clean up file names (remove negative or positive from file name)
    new_catalog = re.sub(r"-catalog-(positive|negative)-\d+\.json", "-catalog.json", input_catalog.name)

    # Copy file to temp dir under new name
    shutil.copy(input_catalog, output_catalog / new_catalog)

    # Extract catalog kind
    kind = str(input_catalog.name).split("-")[0]

    # Execute the command
    invocation = runner.invoke(
        click_main,
        [
            "publish",
            kind,
            "--bucket",
            "travel-sample",
        ],
    )
    if "negative" in input_catalog.name:
        assert invocation.exception is not None
        print(f"Running assertions for negative catalog: {input_catalog.name}")
        assert "Cannot publish a dirty catalog to the DB!" in str(invocation.exception)
    elif "positive" in input_catalog.name:
        print(f"Running assertions for positive catalog: {input_catalog.name}")
        assert kind.upper() in invocation.stdout
        assert f"Uploading the {kind} catalog items to Couchbase" in invocation.stdout
        assert f"Now building the GSI indexes for the {kind} catalog." in invocation.stdout
        assert f"Vector index for the {kind} catalog has been successfully created!" in invocation.stdout


@pytest.mark.regression
def test_publish(tmp_path, isolated_server_factory):
    """
    This test performs the following checks:
        1. command does not publish to kv when catalog is dirty
        2. command publishes to kv when catalog is clean
        3. command publishes catalogs when kind=tool/prompt
           but does not check for kind=all
        4. command ensures data is upserted and indexes created
    """
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        for catalog in (pathlib.Path(__file__).parent / "resources" / "publish_catalog").rglob("*-1.json"):
            publish_catalog(runner, catalog, catalog_folder)


@pytest.mark.regression
def test_find(tmp_path, isolated_server_factory):
    """
    This test performs the following checks:
    1. command executes only for kind=tool assuming same behaviour for prompt
    2. command includes search for dirty versions of tool
    3. command tests the find capability and not recall/accuracy
    """
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        catalog = pathlib.Path(__file__).parent / "resources" / "find_catalog" / "tool-catalog-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)

        # DB find
        invocation = runner.invoke(
            click_main,
            [
                "find",
                "tool",
                "-db",
                "--bucket",
                "travel-sample",
                "--query",
                "'get blogs of interest'",
                "-cid",
                "fe25a5755bfa9af68e1f1fae9ac45e9e37b37611",
            ],
        )
        output = invocation.stdout
        print("\nRan assertion for db find without limit clause (default 1 item is returned)")
        assert "1 result(s) returned from the catalog." in output

        output = runner.invoke(
            click_main,
            [
                "find",
                "tool",
                "-db",
                "--bucket",
                "travel-sample",
                "--query",
                "'get blogs of interest'",
                "--limit",
                "3",
                "-cid",
                "fe25a5755bfa9af68e1f1fae9ac45e9e37b37611",
            ],
        ).stdout
        print("Ran assertion for db find with limit=3")
        assert "3 result(s) returned from the catalog." in output

        # Local find
        output = runner.invoke(
            click_main,
            [
                "find",
                "tool",
                "-local",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
            ],
        ).stdout
        print("\nRan assertion for local find without limit clause (default 1 item is returned)")
        assert "1 result(s) returned from the catalog." in output

        output = runner.invoke(
            click_main,
            [
                "find",
                "tool",
                "-local",
                "--query",
                "'get blogs of interest'",
                "--include-dirty",
                "--limit",
                "3",
            ],
        ).stdout
        print("Ran assertion for local find with limit=3")
        assert "3 result(s) returned from the catalog." in output


@pytest.mark.regression
def test_status(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    print("\n\n")

    # Case 1 - catalog does not exist locally
    output = runner.invoke(click_main, ["status"]).stdout
    expected_response_tool = "local catalog of kind tool does not exist yet"
    expected_response_prompt = "local catalog of kind prompt does not exist yet"
    print("Ran assertion for local status when no catalog exists")
    assert expected_response_tool in output
    assert expected_response_prompt in output

    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()
        catalog = pathlib.Path(__file__).parent / "resources" / "find_catalog" / "tool-catalog-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)

        # Case 2 - tool catalog exists locally (testing for only one kind of catalog)
        output = runner.invoke(click_main, ["status", "tool", "--include-dirty"]).stdout
        print("Ran assertion for local status when tool catalog exists")
        expected_response_local = "local catalog info:\n	path            : .agent-catalog/tool-catalog.json"
        assert expected_response_local in output

        # Case 3 - tool catalog exists in db (this test runs after publish test)
        output = runner.invoke(
            click_main, ["status", "tool", "--include-dirty", "--status-db", "--bucket", "travel-sample"]
        ).stdout
        expected_response = "db catalog info"
        print("Ran assertion for db status when tool catalog exists")
        assert expected_response in output

        # Case 4 - compare the two catalogs
        output = runner.invoke(
            click_main, ["status", "tool", "--compare", "--bucket", "travel-sample", "--include-dirty"]
        ).stdout
        expected_response_db_path = "path            : travel-sample.agent_catalog.tool"
        print("Ran assertion for compare status when tool catalog exists both locally and in db")
        assert expected_response_db_path in output
        assert expected_response in output
        assert expected_response_local in output


@pytest.mark.regression
def test_clean(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
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

        runner.invoke(click_main, ["clean", "local", "all", "-y"])

        print("\n\nRan assertion for local clean")
        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()

        # DB clean
        catalog_folder.mkdir()
        catalog = pathlib.Path(__file__).parent / "resources" / "find_catalog" / "tool-catalog-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)
        runner.invoke(click_main, ["clean", "db", "-y", "--bucket", "travel-sample", "all"])

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

        # Test our status after clean
        output = runner.invoke(
            click_main, ["status", "tool", "--include-dirty", "--status-db", "--bucket", "travel-sample"]
        ).stdout
        expected_response_db = (
            "ERROR: db catalog of kind tool does not exist yet: please use the publish command by specifying the kind."
        )
        print("\n\nRan assertion for db status when tool catalog does not exist in db")
        assert expected_response_db in output


@pytest.mark.regression
def test_execute(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )

        print("Starting tests for execute command on local catalog...")

        output = runner.invoke(click_main, ["execute", "--name", "random_tool", "-local"]).stdout
        assert "No catalog items found" in output

        with patch("click.prompt", side_effect=["BVC"]):
            output = runner.invoke(click_main, ["execute", "--name", "check_if_airport_exists", "-local"]).stdout
            assert "True" in output

        with patch("click.prompt", side_effect=["ABC"]):
            output = runner.invoke(click_main, ["execute", "--name", "check_if_airport_exists", "-local"]).stdout
            assert "False" in output

        with patch("click.prompt", side_effect=["BVC"]):
            output = runner.invoke(click_main, ["execute", "--query", "is airport valid", "-local"]).stdout
            assert "True" in output

        with patch("click.prompt", side_effect=["ABC"]):
            output = runner.invoke(click_main, ["execute", "--query", "is airport valid", "-local"]).stdout
            assert "False" in output

        print("Completed testing execute command on local catalog.")


@pytest.mark.skip
@pytest.mark.regression
def test_publish_multiple_nodes(tmp_path):
    # TODO: Setup multinode cluster for test environment
    pass


@pytest.mark.regression
def test_publish_different_versions(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog_folder.mkdir()

        catalog = pathlib.Path(__file__).parent / "resources" / "publish_catalog" / "prompt-catalog-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)
        catalog = pathlib.Path(__file__).parent / "resources" / "publish_catalog" / "prompt-catalog-positive-2.json"
        publish_catalog(runner, catalog, catalog_folder)
        cluster = couchbase.cluster.Cluster(
            DEFAULT_COUCHBASE_CONN_STRING,
            couchbase.options.ClusterOptions(
                authenticator=couchbase.auth.PasswordAuthenticator(
                    DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD
                ),
            ),
        )
        query = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompt_catalog;")
        for row in query:
            assert row == 4
        query = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompt_metadata;")
        for row in query:
            assert row == 2


@pytest.mark.smoke
def test_ls_local_empty_notindexed(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # when the repo is empty
        output = runner.invoke(click_main, ["ls", "-local"]).stdout
        assert "Searching" not in output

        # when there are tools and prompts, but are not indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.NON_INDEXED_ALL_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["ls", "-local"]).stdout
        assert "Searching" not in output


@pytest.mark.smoke
def test_ls_local_only_tools(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # when only tools are indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["ls", "tool", "-local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["ls", "prompt", "-local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_only_prompts(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # when only prompts are indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["ls", "prompt", "-local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["ls", "tool", "-local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_both_tools_prompts(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # when there are both tools and prompts
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["ls", "prompt", "-local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["ls", "tool", "-local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["ls", "-local"]).stdout
        assert "PROMPT" in output and "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 2


@pytest.mark.smoke
def test_init_local(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(click_main, ["init", "local", "catalog"])
        files_present = os.listdir()
        assert (
            ".agent-catalog" in files_present
            and ".agent-activity" not in files_present
            and ".model-cache" not in files_present
        )

        runner.invoke(click_main, ["init", "local", "auditor"])
        files_present = os.listdir()
        assert (
            ".agent-catalog" in files_present
            and ".agent-activity" in files_present
            and ".model-cache" not in files_present
        )

        runner.invoke(click_main, ["init", "local", "model"])
        files_present = os.listdir()
        assert (
            ".agent-catalog" in files_present and ".agent-activity" in files_present and ".model-cache" in files_present
        )


@pytest.mark.smoke
def test_init_local_all(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(click_main, ["init", "local", "all"])
        files_present = os.listdir()
        assert (
            ".agent-catalog" in files_present and ".agent-activity" in files_present and ".model-cache" in files_present
        )
