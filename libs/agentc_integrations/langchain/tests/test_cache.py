import click.testing
import langchain_openai
import pathlib
import pytest

from agentc_cli.main import click_main
from agentc_langchain.cache import cache
from agentc_testing.catalog import EnvironmentKind
from agentc_testing.catalog import environment_factory
from agentc_testing.server import connection_factory
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory
_ = connection_factory
_ = environment_factory


@pytest.mark.slow
def test_exact_cache(tmp_path, environment_factory, isolated_server_factory, connection_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )

        # TODO (GLENN): Use a fake chat model here...
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
        cached_model = cache(chat_model, kind="exact")
        cached_model.invoke("Hello, how are you doing today?")

        # We should have a value in the cache collection.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.langchain_llm_cache l
            SELECT VALUE l
        """).execute()
        assert len(results) == 1
        assert "Hello, how are you doing today?" in str(results[0]["prompt"])


@pytest.mark.slow
def test_semantic_cache(tmp_path, environment_factory, isolated_server_factory, connection_factory):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        isolated_server_factory(pathlib.Path(td) / ".couchbase")
        environment_factory(
            directory=pathlib.Path(td),
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )

        # TODO (GLENN): Use a fake chat model here...
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
        embeddings = langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")
        cached_model = cache(chat_model, kind="semantic", embeddings=embeddings)
        cached_model.invoke("Hello, how are you doing today?")

        # We should have a value in the cache collection.
        cluster = connection_factory()
        results = cluster.query("""
            FROM `travel-sample`.agent_activity.langchain_llm_cache l
            SELECT VALUE l
        """).execute()
        assert len(results) == 1
        assert "embedding" in results[0]
        assert "Hello, how are you doing today?" in str(results[0])
