import click
import click.testing
import os
import pathlib
import pytest

from agentc import Catalog
from agentc_cli.main import click_main
from agentc_core.catalog.catalog import Prompt
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory


@pytest.mark.smoke
def test_local_tool_provider(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        catalog = Catalog()
        tools = catalog.find("tool", query="searching travel blogs")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.smoke
def test_local_inputs_provider(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        catalog = Catalog()
        prompt: Prompt = catalog.find("prompt", query="asking a user their location")[0]
        assert prompt.tools == []
        assert prompt.meta.name == "get_user_location"


@pytest.mark.smoke
def test_local_provider(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        catalog = Catalog()
        prompt: list[Prompt] = catalog.find("prompt", query="asking a user their location")
        tools = catalog.find("tool", query="searching travel blogs")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"
        assert prompt[0].tools == []
        assert prompt[0].meta.name == "get_user_location"


@pytest.mark.slow
def test_db_tool_provider(tmp_path, isolated_server_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        os.remove((pathlib.Path(td) / DEFAULT_CATALOG_FOLDER / DEFAULT_TOOL_CATALOG_FILE).absolute())
        catalog = Catalog(bucket="travel-sample")
        tools = catalog.find("tool", query="searching travel blogs using user interests")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.skip
@pytest.mark.slow
def test_db_inputs_provider(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.slow
def test_chain_tool_provider(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.slow
def test_chain_inputs_provider(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass
