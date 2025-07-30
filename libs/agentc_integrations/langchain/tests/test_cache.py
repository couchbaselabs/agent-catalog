import click_extra.testing
import couchbase.cluster
import langchain_openai
import pathlib
import pytest
import typing

from agentc_cli.main import agentc
from agentc_langchain.cache import cache
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
def test_exact_cache(
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
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )

        # TODO (GLENN): Use a fake chat model here...
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o-mini")
        cached_model = cache(chat_model, kind="exact", create_if_not_exists=True)
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
def test_semantic_cache(
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
            env_kind=EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
            click_runner=click_extra.testing.ExtraCliRunner(),
            click_command=agentc,
        )

        # TODO (GLENN): Use a fake chat model here...
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o-mini")
        embeddings = langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")
        cached_model = cache(chat_model, kind="semantic", embeddings=embeddings, create_if_not_exists=True)
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
