import click_extra.testing
import couchbase.cluster
import llama_index.core.llms
import llama_index.llms.openai
import pathlib
import pytest
import typing

from agentc_cli.main import agentc
from agentc_core.catalog import Catalog
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_llamaindex.chat import Callback
from agentc_testing.catalog import Environment
from agentc_testing.catalog import EnvironmentKind
from agentc_testing.catalog import environment_factory
from agentc_testing.directory import temporary_directory
from agentc_testing.server import connection_factory
from agentc_testing.server import shared_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = shared_server_factory
_ = connection_factory
_ = environment_factory
_ = temporary_directory


@pytest.mark.slow
def test_complete(
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
            env_kind=EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog(bucket="travel-sample")
        span = catalog.Span(name="default")

        # TODO (GLENN): Use a fake chat model here...
        chat_model = llama_index.llms.openai.OpenAI(model="gpt-4o")
        chat_model.callback_manager.add_handler(Callback(span=span))
        chat_model.complete("Hello, how are you doing today?")

        # We should have seven logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # ENTER + ENTER + HUMAN + HUMAN + LLM + EXIT + EXIT
            assert len(fp.readlines()) == 7

        # ...and six logs in our Couchbase instance.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.logs l
            SELECT VALUE l
        """).execute()
        assert len(results) == 7


# We test remote logging in the test above, so we'll stick to local log testing from here out.
@pytest.mark.smoke
def test_chat(
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
        catalog = Catalog(bucket="travel-sample")
        span = catalog.Span(name="default")

        # TODO (GLENN): Use a fake chat model here...
        chat_model = llama_index.llms.openai.OpenAI(model="gpt-4o")
        chat_model.callback_manager.add_handler(Callback(span=span))
        chat_model.chat(
            [
                llama_index.core.llms.ChatMessage(
                    role="system", content="You are a pirate with a colorful personality"
                ),
                llama_index.core.llms.ChatMessage(role="user", content="What is your name"),
            ]
        )

        # We should have nine logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # ENTER + ENTER + SYSTEM + HUMAN + SYSTEM + HUMAN + LLM + EXIT + EXIT
            assert len(fp.readlines()) == 9


@pytest.mark.skip
@pytest.mark.slow
def test_tool_calling():
    # TODO (GLENN): Finish me!
    pass
