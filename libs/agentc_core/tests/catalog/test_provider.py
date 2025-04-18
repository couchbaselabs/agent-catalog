import click_extra
import click_extra.testing
import os
import pathlib
import pytest
import typing

from agentc import Catalog
from agentc_cli.main import agentc
from agentc_core.catalog.catalog import Prompt
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_testing.catalog import Environment
from agentc_testing.catalog import EnvironmentKind
from agentc_testing.catalog import environment_factory
from agentc_testing.directory import temporary_directory
from agentc_testing.server import shared_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = shared_server_factory
_ = environment_factory
_ = temporary_directory


@pytest.mark.smoke
def test_local_tool_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog()
        tools = catalog.find("tool", query="searching travel blogs")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.smoke
def test_local_tool_provider_with_decorator(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog(tool_decorator=lambda x: {"tool": x.func})
        tools = catalog.find("tool", query="searching travel blogs")
        assert len(tools) == 1
        assert isinstance(tools[0], dict)
        assert tools[0]["tool"].__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.smoke
def test_local_inputs_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_PROMPTS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog()
        prompt: Prompt = catalog.find("prompt", query="asking a user their location")[0]
        assert prompt.tools == []
        assert prompt.meta.name == "get_user_location"


@pytest.mark.smoke
def test_local_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog()
        prompt: list[Prompt] = catalog.find("prompt", query="asking a user their location")
        tools = catalog.find("tool", query="searching travel blogs")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"
        assert prompt[0].tools == []
        assert prompt[0].meta.name == "get_user_location"


@pytest.mark.slow
def test_db_tool_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        shared_server_factory()
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        os.remove((pathlib.Path(td) / DEFAULT_CATALOG_FOLDER / DEFAULT_TOOL_CATALOG_FILE).absolute())
        catalog = Catalog(bucket="travel-sample")
        tools = catalog.find("tool", query="searching travel blogs using user interests")
        assert len(tools) == 1
        assert tools[0].func.__name__ == "get_travel_blog_snippets_from_user_interests"


@pytest.mark.skip
@pytest.mark.slow
def test_db_inputs_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.slow
def test_chain_tool_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.slow
def test_chain_inputs_provider(
    temporary_directory: typing.Generator[pathlib.Path, None, None],
    environment_factory: typing.Callable[..., Environment],
    shared_server_factory: typing.Callable[[], ...],
):
    # TODO (GLENN): Finish me!
    pass
