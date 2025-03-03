import click.testing
import llama_index.core.llms
import llama_index.llms.openai
import pathlib
import pytest

from agentc_cli.main import click_main
from agentc_core.catalog import Catalog
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_llamaindex.chat import Callback
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import connection_factory
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory
_ = connection_factory


@pytest.mark.slow
def test_complete(tmp_path, isolated_server_factory, connection_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.PUBLISHED_PROMPTS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
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
def test_chat(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
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
