import click_extra.testing
import couchbase.cluster
import git
import json
import os
import pathlib
import pytest
import re
import requests
import shutil
import typing
import uuid

from agentc_cli.main import agentc
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_testing.catalog import Environment
from agentc_testing.catalog import EnvironmentKind
from agentc_testing.catalog import environment_factory
from agentc_testing.directory import temporary_directory
from agentc_testing.server import DEFAULT_COUCHBASE_BUCKET
from agentc_testing.server import DEFAULT_COUCHBASE_PASSWORD
from agentc_testing.server import DEFAULT_COUCHBASE_USERNAME
from agentc_testing.server import connection_factory
from agentc_testing.server import shared_server_factory
from unittest.mock import patch

# This is to keep ruff from falsely flagging this as unused.
_ = shared_server_factory
_ = connection_factory
_ = environment_factory
_ = temporary_directory


@pytest.mark.smoke
def test_index(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        env = environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.EMPTY,
            click_runner=runner,
            click_command=agentc,
        )

        env.repository = git.Repo.init(td)
        env.repository.index.commit("Initial commit")
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
        invocation = runner.invoke(agentc, ["index", str(tool_folder.absolute()), "--no-prompts"])

        # We should see 11 files scanned and 12 tools indexed.
        output = invocation.output
        assert "Crawling" in output
        assert "Generating embeddings" in output
        assert "Catalog successfully indexed" in output
        assert "0/11" in output
        assert "0/12" in output


@pytest.mark.slow
def test_publish_positive_1(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        result = runner.invoke(agentc, ["init", "catalog", "--no-local", "--db"])
        assert "GSI metadata index for the has been successfully created!" in result.output
        assert "Vector index for the tool catalog has been successfully created!" in result.output
        assert "Vector index for the prompt catalog has been successfully created!" in result.output

        result = runner.invoke(agentc, ["publish"])
        assert "Uploading the tool catalog items to Couchbase" in result.output
        assert "Uploading the prompt catalog items to Couchbase" in result.output

        cluster = connection_factory()
        t1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;").execute()
        t2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;").execute()
        assert t1[0] == 24
        assert t2[0] == 12


@pytest.mark.slow
def test_publish_negative_1(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_DIRTY_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        result = runner.invoke(agentc, ["init", "catalog", "--no-local", "--db"])
        assert "GSI metadata index for the has been successfully created!" in result.output
        assert "Vector index for the tool catalog has been successfully created!" in result.output
        assert "Vector index for the prompt catalog has been successfully created!" in result.output

        result = runner.invoke(agentc, ["publish"])
        assert "Cannot publish a dirty catalog to the DB!" in str(result.exception)

        cluster = connection_factory()
        t1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;").execute()
        t2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;").execute()
        assert t1[0] == 0
        assert t2[0] == 0


@pytest.mark.slow
def test_publish_positive_2(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        result = runner.invoke(agentc, ["init", "catalog", "--no-local", "--db"])
        assert "GSI metadata index for the has been successfully created!" in result.output
        assert "Vector index for the tool catalog has been successfully created!" in result.output
        assert "Vector index for the prompt catalog has been successfully created!" in result.output

        result = runner.invoke(agentc, ["publish", "tools"])
        assert "Uploading the tool catalog items to Couchbase" in result.output

        cluster = connection_factory()
        t1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;").execute()
        t2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;").execute()
        assert t1[0] == 24
        assert t2[0] == 0


@pytest.mark.slow
def test_publish_positive_3(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        result = runner.invoke(agentc, ["init", "catalog", "--no-local", "--db"])
        assert "GSI metadata index for the has been successfully created!" in result.output
        assert "Vector index for the tool catalog has been successfully created!" in result.output
        assert "Vector index for the prompt catalog has been successfully created!" in result.output

        result = runner.invoke(agentc, ["publish", "prompts"])
        assert "Uploading the prompt catalog items to Couchbase" in result.output

        cluster = connection_factory()
        t1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;").execute()
        t2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;").execute()
        assert t1[0] == 0
        assert t2[0] == 12


@pytest.mark.slow
def test_find(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    """
    This test performs the following checks:
    1. command executes only for kind=tool assuming same behaviour for prompt
    2. command includes search for dirty versions of tool
    3. command tests the find capability and not recall/accuracy
    """
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        env = environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        # DB find
        cid = env.repository.head.commit.binsha.hex()
        invocation = runner.invoke(
            agentc,
            [
                "find",
                "tools",
                "--db",
                "--query",
                "'get blogs of interest'",
                "-cid",
                cid,
            ],
        )
        output = invocation.stdout
        assert "1 result(s) returned from the catalog." in output

        output = runner.invoke(
            agentc,
            ["find", "tools", "--db", "--query", "'get blogs of interest'", "--limit", "3", "-cid", cid],
        ).stdout
        assert "3 result(s) returned from the catalog." in output

        # Local find
        output = runner.invoke(
            agentc,
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
            agentc,
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
def test_status(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        os.chdir(td)

        # Case 1 - catalog does not exist locally
        output = runner.invoke(agentc, ["status"])
        assert "Local catalog not found " in str(output.exception)
        assert isinstance(output.exception, ValueError)

        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        # Case 2 - tool catalog exists locally (testing for only one kind of catalog)
        output = runner.invoke(agentc, ["status", "tools", "--dirty"]).stdout
        assert "local catalog info:\n	path            :" in output
        assert ".agent-catalog/tools.json" in output

        # Case 3 - tool catalog exists in db (this test runs after publish test)
        output = runner.invoke(agentc, ["status", "tools", "--dirty", "--no-local", "--db"]).stdout
        assert "db catalog info" in output

        # Case 4 - compare the two catalogs
        output = runner.invoke(agentc, ["status", "tools", "--local", "--db", "--dirty"]).stdout
        assert "local catalog info:\n	path            :" in output
        assert ".agent-catalog/tools.json" in output
        assert "db catalog info" in output


@pytest.mark.smoke
def test_local_clean(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.EMPTY,
            click_runner=runner,
            click_command=agentc,
        )
        runner.invoke(agentc, ["init", "catalog", "--no-db"])
        catalog_folder = pathlib.Path(td) / DEFAULT_CATALOG_FOLDER

        # Local clean
        dummy_file_1 = catalog_folder / DEFAULT_PROMPT_CATALOG_FILE
        dummy_file_2 = catalog_folder / DEFAULT_TOOL_CATALOG_FILE
        with dummy_file_1.open("w") as fp:
            fp.write("dummy content")
        with dummy_file_2.open("w") as fp:
            fp.write("more dummy content")

        assert runner.invoke(agentc, ["clean", "catalog", "--no-db", "-y"]).exit_code == 0
        assert not dummy_file_1.exists()
        assert not dummy_file_2.exists()


@pytest.mark.skip
@pytest.mark.smoke
def test_local_clean_with_date(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    # TODO (GLENN): Implement me!
    pass


@pytest.mark.slow
def test_db_clean(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )
        runner.invoke(
            agentc,
            [
                "clean",
                "catalog",
                "-y",
            ],
        )

        # Get all scopes in bucket
        response = requests.request(
            "GET",
            f"http://localhost:8091/pools/default/buckets/{DEFAULT_COUCHBASE_BUCKET}/scopes",
            auth=(DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD),
            verify=False,
        )
        scopes = json.loads(response.text)["scopes"]

        # Verify DEFAULT_CATALOG_SCOPE is deleted
        is_scope_present = False
        for scope in scopes:
            if scope["name"] == DEFAULT_CATALOG_SCOPE:
                is_scope_present = True
                break

        assert not is_scope_present, f"Clean DB failed as scope {DEFAULT_CATALOG_SCOPE} is present in DB."

        # Test our status after clean
        output = runner.invoke(agentc, ["status", "tools", "--dirty", "--db"]).stdout
        expected_response_db = (
            "ERROR: db catalog of kind tool does not exist yet: please use the publish command by specifying the kind."
        )
        assert expected_response_db in output


@pytest.mark.skip
@pytest.mark.smoke
def test_db_clean_with_date(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    # TODO (GLENN): Implement me!
    pass


@pytest.mark.smoke
def test_execute(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        output = runner.invoke(agentc, ["execute", "--name", "random_tool", "--local"]).stdout
        assert "No catalog items found" in output

        with patch("click_extra.prompt", side_effect=["BVC"]):
            output = runner.invoke(agentc, ["execute", "--name", "check_if_airport_exists", "--local"]).stdout
            assert "True" in output

        with patch("click_extra.prompt", side_effect=["ABC"]):
            output = runner.invoke(agentc, ["execute", "--name", "check_if_airport_exists", "--local"]).stdout
            assert "False" in output

        with patch("click_extra.prompt", side_effect=["BVC"]):
            output = runner.invoke(agentc, ["execute", "--query", "is airport valid", "--local"]).stdout
            assert "True" in output

        with patch("click_extra.prompt", side_effect=["ABC"]):
            output = runner.invoke(agentc, ["execute", "--query", "is airport valid", "--local"]).stdout
            assert "False" in output


@pytest.mark.skip
@pytest.mark.slow
def test_publish_multiple_nodes(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    # TODO: Setup multinode cluster for test environment
    pass


@pytest.mark.slow
def test_publish_different_versions(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )

        cluster = connection_factory()
        q1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;")
        q2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;")
        initial_prompt_count = int(q1.execute()[0])
        initial_tool_count = int(q2.execute()[0])

        # We will now go through another commit-index-publish sequence. First, our commit...
        repo: git.Repo = git.Repo.init(td)
        with (pathlib.Path(td) / "README.md").open("a") as f:
            f.write("\nI'm dirty now!")
        repo.index.add(["README.md"])
        n1 = len(list(repo.iter_commits()))
        repo.index.commit("Next commit")
        n2 = len(list(repo.iter_commits()))
        assert n1 < n2

        # ...now, our index...
        result = runner.invoke(agentc, ["index", "tools", "prompts"])
        assert "Catalog successfully indexed" in result.output

        # ...and finally, our publish.
        result = runner.invoke(agentc, ["publish"])
        assert "Uploading the prompt catalog items to Couchbase" in result.output
        assert "Uploading the tool catalog items to Couchbase" in result.output

        cluster = connection_factory()
        q1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;")
        assert q1.execute()[0] == initial_prompt_count * 2
        q2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;")
        assert q2.execute()[0] == initial_tool_count * 2
        q3 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.metadata;")
        assert q3.execute()[0] == 4


@pytest.mark.smoke
def test_ls_local_empty_notindexed(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        os.chdir(td)

        # when the repo is empty
        output = runner.invoke(agentc, ["ls", "--local", "--no-db"]).stderr
        assert "Could not find .git directory. Please run agentc within a git repository." in output

        # when there are tools and prompts, but are not indexed
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.NON_INDEXED_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )
        output = runner.invoke(agentc, ["ls", "--local", "--no-db"]).stderr
        assert "Could not find local catalog at" in output


@pytest.mark.smoke
def test_ls_local_only_tools(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        # when only tools are indexed
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )
        output = runner.invoke(agentc, ["-v", "ls", "tools", "--local", "--no-db"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(agentc, ["-v", "ls", "prompts", "--local", "--no-db"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_only_prompts(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        # when only prompts are indexed
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )
        output = runner.invoke(agentc, ["-v", "ls", "prompts", "--local", "--no-db"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(agentc, ["-v", "ls", "tools", "--local", "--no-db"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 0


@pytest.mark.smoke
def test_ls_local_both_tools_prompts(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        # when there are both tools and prompts
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=runner,
            click_command=agentc,
        )
        output = runner.invoke(agentc, ["-v", "ls", "prompts", "--local", "--no-db"]).stdout
        assert "PROMPT" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(agentc, ["-v", "ls", "tools", "--local", "--no-db"]).stdout
        assert "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 1
        output = runner.invoke(agentc, ["-v", "ls", "--local"]).stdout
        assert "PROMPT" in output and "TOOL" in output and len(re.findall(r"\b1\.\s.+", output)) == 2


@pytest.mark.smoke
def test_init_local(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        os.chdir(td)

        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(agentc, ["init", "catalog", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" not in files_present

        runner.invoke(agentc, ["init", "activity", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" in files_present


@pytest.mark.smoke
def test_init_local_all(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        os.chdir(td)
        files_present = os.listdir()
        assert ".agent-catalog" not in files_present and ".agent-activity" not in files_present

        runner.invoke(agentc, ["init", "catalog", "activity", "--local", "--no-db"])
        files_present = os.listdir()
        assert ".agent-catalog" in files_present and ".agent-activity" in files_present


@pytest.mark.slow
def test_init_db(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
    connection_factory: typing.Callable[[], couchbase.cluster.Cluster],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.EMPTY,
            click_runner=runner,
            click_command=agentc,
        )
        result = runner.invoke(agentc, ["init", "catalog", "--db"])
        assert result.exit_code == 0
        assert "GSI metadata index for the has been successfully created!" in result.output
        assert "Vector index for the tool catalog has been successfully created!" in result.output

        # TODO (GLENN): Check if the proper indexes have been created.
        cluster = connection_factory()
        t1 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.tools;").execute()
        t2 = cluster.query("SELECT VALUE COUNT(*) FROM `travel-sample`.agent_catalog.prompts;").execute()
        assert t1[0] == 0
        assert t2[0] == 0
