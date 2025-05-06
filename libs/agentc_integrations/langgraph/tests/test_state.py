import click_extra.testing
import couchbase.cluster
import langchain_openai
import langgraph.prebuilt
import pathlib
import pytest
import typing

from agentc_cli.main import agentc
from agentc_langgraph.state import AsyncCheckpointSaver
from agentc_langgraph.state import CheckpointSaver
from agentc_langgraph.state import initialize
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
def test_checkpoint_saver(
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
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
        agent = langgraph.prebuilt.create_react_agent(
            model=chat_model, tools=list(), checkpointer=CheckpointSaver(create_if_not_exists=True)
        )
        config = {"configurable": {"thread_id": "1"}}
        agent.invoke({"messages": [("human", "what's the weather in sf")]}, config)

        # We should have a value in the thread and tuples collection.
        cluster = connection_factory()
        results = cluster.query("""
            (
                SELECT VALUE l
                FROM `travel-sample`.agent_activity.langgraph_checkpoint_thread l
                LIMIT 1
            )
            UNION ALL
            (
                SELECT VALUE l
                FROM `travel-sample`.agent_activity.langgraph_checkpoint_tuple l
                LIMIT 1
            )
        """).execute()
        assert len(results) == 2


@pytest.mark.skip
@pytest.mark.asyncio
@pytest.mark.slow
async def test_async_checkpoint_saver(
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
        chat_model = langchain_openai.ChatOpenAI(name="gpt-4o")
        initialize()
        agent = langgraph.prebuilt.create_react_agent(
            model=chat_model, tools=list(), checkpointer=await AsyncCheckpointSaver.create()
        )
        config = {"configurable": {"thread_id": "1"}}
        await agent.ainvoke({"messages": [("human", "what's the weather in sf")]}, config)

        # We should have a value in the thread and tuples collection.
        cluster = connection_factory()
        results = cluster.query("""
            (
                SELECT VALUE l
                FROM `travel-sample`.agent_activity.langgraph_checkpoint_thread l
                LIMIT 1
            )
            UNION ALL
            (
                SELECT VALUE l
                FROM `travel-sample`.agent_activity.langgraph_checkpoint_tuple l
                LIMIT 1
            )
        """).execute()
        assert len(results) == 2
