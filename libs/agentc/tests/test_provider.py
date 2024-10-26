import click
import click.testing
import os
import pathlib
import pytest

from agentc import Provider
from agentc_cli.main import click_main
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import get_isolated_server

# This is to keep ruff from falsely flagging this as unused.
_ = get_isolated_server


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
        os.chdir(td)
        provider = Provider()
        tools = provider.get_tools_for("searching travel blogs")
        assert len(tools) == 1
        assert tools[0].__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.smoke
def test_local_prompt_provider(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        os.chdir(td)
        provider = Provider()
        prompt = provider.get_prompt_for("asking a user their location")
        assert prompt.tools is None
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
        os.chdir(td)
        provider = Provider()
        prompt = provider.get_prompt_for("asking a user their location")
        tools = provider.get_tools_for("searching travel blogs")
        assert len(tools) == 1
        assert tools[0].__name__ == "get_travel_blog_snippets_from_user_interests"
        assert prompt.tools is None
        assert prompt.meta.name == "get_user_location"


@pytest.mark.regression
def test_db_tool_provider(tmp_path, get_isolated_server):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        os.chdir(td)
        os.remove((pathlib.Path(td) / DEFAULT_CATALOG_FOLDER / DEFAULT_TOOL_CATALOG_NAME).absolute())
        provider = Provider(bucket="travel-sample")
        tools = provider.get_tools_for("searching travel blogs")
        assert len(tools) == 1
        assert tools[0].__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.skip
@pytest.mark.regression
def test_db_prompt_provider(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_tool_provider(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_prompt_provider(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass
