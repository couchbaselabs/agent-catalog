import click_extra.testing
import langchain_openai
import pathlib
import pytest

from agentc_cli.main import agentc
from agentc_core.catalog import Catalog
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_langchain.chat import Callback
from agentc_langchain.chat import audit
from agentc_testing.catalog import EnvironmentKind
from agentc_testing.catalog import environment_factory
from agentc_testing.directory import temporary_directory
from agentc_testing.server import connection_factory
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory
_ = connection_factory
_ = environment_factory
_ = temporary_directory


@pytest.mark.slow
def test_audit(temporary_directory, environment_factory, isolated_server_factory, connection_factory):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog(bucket="travel-sample")
        span = catalog.Span(name="default")

        # TODO (GLENN): Use a fake chat model here...
        chat_model = audit(langchain_openai.ChatOpenAI(name="gpt-4o"), span=span)
        chat_model.invoke("Hello, how are you doing today?")

        # We should have four logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # BEGIN + USER + CHAT-COMPLETION + END
            assert len(fp.readlines()) == 4

        # ...and four logs in our Couchbase instance.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.logs l
            SELECT VALUE l
        """).execute()
        assert len(results) == 4


@pytest.mark.slow
def test_callback(temporary_directory, environment_factory, isolated_server_factory, connection_factory):
    runner = click_extra.testing.ExtraCliRunner()
    with runner.isolated_filesystem(temp_dir=temporary_directory) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )
        catalog = Catalog(bucket="travel-sample")
        span = catalog.Span(name="default")

        # TODO (GLENN): Use a fake chat model here...
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o", callbacks=[Callback(span=span)])
        chat_model.invoke("Hello, how are you doing today?")

        # We should have five logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # BEGIN + REQUEST-HEADER + USER + CHAT-COMPLETION + END
            assert len(fp.readlines()) == 5

        # ...and five logs in our Couchbase instance.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.logs l
            SELECT VALUE l
        """).execute()
        assert len(results) == 5
