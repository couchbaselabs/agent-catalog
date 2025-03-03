import click.testing
import langchain_openai
import pathlib
import pytest

from agentc_cli.main import click_main
from agentc_core.catalog import Catalog
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_langchain.chat import Callback
from agentc_langchain.chat import audit
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import connection_factory
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory
_ = connection_factory


@pytest.mark.slow
def test_audit(tmp_path, isolated_server_factory, connection_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )
        catalog = Catalog(bucket="travel-sample")
        span = catalog.Span(name="default")

        # TODO (GLENN): Use a fake chat model here...
        chat_model = audit(langchain_openai.ChatOpenAI(name="gpt-4o"), span=span)
        chat_model.invoke("Hello, how are you doing today?")

        # We should have two logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            assert len(fp.readlines()) == 2

        # ...and two logs in our Couchbase instance.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.logs l
            SELECT VALUE l
        """).execute()
        assert len(results) == 2


@pytest.mark.slow
def test_callback(tmp_path, isolated_server_factory, connection_factory):
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
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o", callbacks=[Callback(span=span)])
        chat_model.invoke("Hello, how are you doing today?")

        # We should have six logs in our local FS...
        with (pathlib.Path(td) / DEFAULT_ACTIVITY_FOLDER / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # ENTER + ENTER + HUMAN + EXIT + LLM + EXIT
            assert len(fp.readlines()) == 6

        # ...and six logs in our Couchbase instance.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.logs l
            SELECT VALUE l
        """).execute()
        assert len(results) == 6
