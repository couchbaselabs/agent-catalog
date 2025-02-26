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
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
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
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        os.chdir(td)

        repo = git.Repo.init(td)
        repo.index.commit("Initial commit")
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        activity_folder = pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER
        tool_folder = pathlib.Path(td) / "tools"
        catalog_folder.mkdir()
        activity_folder.mkdir()
        tool_folder.mkdir()

        # Copy all positive tool into our tools.
        resources_folder = pathlib.Path(__file__).parent / "resources" / "index"
        for tool in resources_folder.rglob("*positive*"):
            if tool.suffix == ".pyc":
                continue
            pathlib.Path(tool_folder / tool.parent.name).mkdir(exist_ok=True)
            shutil.copy(tool, tool_folder / tool.parent.name / (uuid.uuid4().hex + tool.suffix))
        shutil.copy(resources_folder / "_good_spec.json", tool_folder / "_good_spec.json")
        invocation = runner.invoke(click_main, ["index", str(tool_folder.absolute()), "--no-prompts"])

        # We should see 11 files scanned and 12 tools indexed.
        output = invocation.output
        assert "Crawling" in output
        assert "Generating embeddings" in output
        assert "Catalog successfully indexed" in output
        assert "0/11" in output
        assert "0/12" in output


# Small helper function to publish to a Couchbase catalog.
def publish_catalog(runner, input_catalog: pathlib.Path, output_catalog: pathlib.Path):
    # Clean up file names (remove negative or positive from file name)
    new_catalog = re.sub(r"-(positive|negative)-\d+\.json", ".json", input_catalog.name)

    # Copy file to temp dir under new name
    shutil.copy(input_catalog, output_catalog / new_catalog)

    # Extract catalog kind
    kind = "tools" if "tools" in input_catalog.name else "prompts"

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
        assert "Cannot publish a dirty catalog to the DB!" in str(invocation.exception)
    elif "positive" in input_catalog.name:
        kind = kind.removesuffix("s")
        assert kind.upper() in invocation.stdout
        assert f"Uploading the {kind} catalog items to Couchbase" in invocation.stdout


@pytest.mark.slow
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
        os.chdir(td)
        runner.invoke(click_main, ["init", "catalog", "--local", "--db"])
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        for catalog in (pathlib.Path(__file__).parent / "resources" / "publish").rglob("*-1.json"):
            publish_catalog(runner, catalog, catalog_folder)


@pytest.mark.slow
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
        os.chdir(td)
        runner.invoke(click_main, ["init", "catalog", "--local", "--db"])
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog = pathlib.Path(__file__).parent / "resources" / "find" / "tools-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)

        # DB find
        invocation = runner.invoke(
            click_main,
            [
                "find",
                "tools",
                "--db",
                "--query",
                "'get blogs of interest'",
                "-cid",
                "fafdf72735d9c60c0b5bfa3101b01f3be13f7cb3",
            ],
        )
        output = invocation.stdout
        assert "1 result(s) returned from the catalog." in output

        output = runner.invoke(
            click_main,
            [
                "find",
                "tools",
                "--db",
                "--query",
                "'get blogs of interest'",
                "--limit",
                "3",
                "-cid",
                "fafdf72735d9c60c0b5bfa3101b01f3be13f7cb3",
            ],
        ).stdout
        assert "3 result(s) returned from the catalog." in output

        # Local find
        output = runner.invoke(
            click_main,
            [
                "find",
                "tools",
                "--local",
                "--query",
                "'get blogs of interest'",
                "--dirty",
            ],
        ).stdout
        assert "1 result(s) returned from the catalog." in output

        output = runner.invoke(
            click_main,
            [
                "find",
                "tools",
                "--local",
                "--query",
                "'get blogs of interest'",
                "--dirty",
                "--limit",
                "3",
            ],
        ).stdout
        assert "3 result(s) returned from the catalog." in output


@pytest.mark.slow
def test_status(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        # Case 1 - catalog does not exist locally
        output = runner.invoke(click_main, ["status"])
        assert "Local catalog not found " in str(output.exception)
        assert isinstance(output.exception, ValueError)

        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        runner.invoke(click_main, ["init", "catalog", "--local", "--db"])
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog = pathlib.Path(__file__).parent / "resources" / "find" / "tools-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)

        # Case 2 - tool catalog exists locally (testing for only one kind of catalog)
        output = runner.invoke(click_main, ["status", "tools", "--dirty"]).stdout
        assert "local catalog info:\n	path            :" in output
        assert ".agent-catalog/tools.json" in output

        # Case 3 - tool catalog exists in db (this test runs after publish test)
        output = runner.invoke(click_main, ["status", "tools", "--dirty", "--db"]).stdout
        assert "db catalog info" in output

        # Case 4 - compare the two catalogs
        output = runner.invoke(click_main, ["status", "tools", "--local", "--db", "--dirty"]).stdout
        assert "local catalog info:\n	path            :" in output
        assert ".agent-catalog/tools.json" in output
        assert "db catalog info" in output


@pytest.mark.slow
def test_clean(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        os.chdir(td)

        runner.invoke(click_main, ["init", "catalog", "--local", "--db"])
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.EMPTY,
            click_runner=runner,
            click_command=click_main,
        )
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER

        # Local clean
        dummy_file_1 = catalog_folder / DEFAULT_PROMPT_CATALOG_FILE
        dummy_file_2 = catalog_folder / DEFAULT_TOOL_CATALOG_FILE
        with dummy_file_1.open("w") as fp:
            fp.write("dummy content")
        with dummy_file_2.open("w") as fp:
            fp.write("more dummy content")

        assert runner.invoke(click_main, ["clean", "catalog", "--no-db", "-y"]).exit_code == 0
        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()

        # DB clean
        catalog_folder.mkdir()
        catalog = pathlib.Path(__file__).parent / "resources" / "find" / "tools-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)
        runner.invoke(
            click_main,
            [
                "clean",
                "catalog",
                "--no-local",
                "-y",
            ],
        )

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

        assert not is_scope_present, f"Clean DB failed as scope {DEFAULT_CATALOG_SCOPE} is present in DB."

        # Test our status after clean
        output = runner.invoke(click_main, ["status", "tools", "--dirty", "--db"]).stdout
        expected_response_db = (
            "ERROR: db catalog of kind tool does not exist yet: please use the publish command by specifying the kind."
        )
        assert expected_response_db in output


@pytest.mark.slow
def test_execute(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        os.chdir(td)

        output = runner.invoke(click_main, ["execute", "--name", "random_tool", "--local"]).stdout
        assert "No catalog items found" in output

        with patch("click.prompt", side_effect=["BVC"]):
            output = runner.invoke(click_main, ["execute", "--name", "check_if_airport_exists", "--local"]).stdout
            assert "True" in output

        with patch("click.prompt", side_effect=["ABC"]):
            output = runner.invoke(click_main, ["execute", "--name", "check_if_airport_exists", "--local"]).stdout
            assert "False" in output

        with patch("click.prompt", side_effect=["BVC"]):
            output = runner.invoke(click_main, ["execute", "--query", "is airport valid", "--local"]).stdout
            assert "True" in output

        with patch("click.prompt", side_effect=["ABC"]):
            output = runner.invoke(click_main, ["execute", "--query", "is airport valid", "--local"]).stdout
            assert "False" in output


@pytest.mark.skip
@pytest.mark.slow
def test_publish_multiple_nodes(tmp_path):
    # TODO: Setup multinode cluster for test environment
    pass


@pytest.mark.slow
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
        os.chdir(td)
        runner.invoke(click_main, ["init", "catalog", "--local", "--db"])

        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER
        catalog = pathlib.Path(__file__).parent / "resources" / "publish" / "prompts-positive-1.json"
        publish_catalog(runner, catalog, catalog_folder)
        catalog = pathlib.Path(__file__).parent / "resources" / "publish" / "prompts-positive-2.json"
        publish_catalog(runner, catalog, catalog_folder)
        cluster = couchbase.cluster.Cluster(
            DEFAULT_COUCHBASE_CONN_STRING,
            couchbase.options.ClusterOptions(
                authenticator=couchbase.auth.PasswordAuthenticator(
                    DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD
                ),
            ),
        )
        query = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;")
        for row in query:
            assert row == 4
        query = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.metadata;")
        for row in query:
            assert row == 2


@pytest.mark.smoke
def test_ls_local_empty_notindexed(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        # when the repo is empty
        output = runner.invoke(click_main, ["ls", "--local"]).stdout
        assert "Searching" not in output

        # when there are tools and prompts, but are not indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.NON_INDEXED_ALL_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["ls", "--local"]).stdout
        assert "Searching" not in output


@pytest.mark.smoke
def test_ls_local_only_tools(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        # when only tools are indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["-v", "ls", "tools", "--local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["-v", "ls", "prompts", "--local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_only_prompts(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        # when only prompts are indexed
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["-v", "ls", "prompts", "--local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["-v", "ls", "tools", "--local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_both_tools_prompts(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        # when there are both tools and prompts
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=click_main,
        )
        output = runner.invoke(click_main, ["-v", "ls", "prompts", "--local"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["-v", "ls", "tools", "--local"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(click_main, ["-v", "ls", "--local"]).stdout
        assert "PROMPT" in output and "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 2


@pytest.mark.smoke
def test_init_local(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)

        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(click_main, ["init", "catalog", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" not in files_present

        runner.invoke(click_main, ["init", "activity", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" in files_present


@pytest.mark.smoke
def test_init_local_all(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        os.chdir(td)
        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(click_main, ["init", "catalog", "activity", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" in files_present
