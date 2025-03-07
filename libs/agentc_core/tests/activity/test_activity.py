import click
import click.testing
import pathlib
import pytest

from agentc import Catalog
from agentc_cli.main import click_main
from agentc_core.activity import GlobalSpan
from agentc_core.activity import Span
from agentc_core.activity.models.content import KeyValueContent
from agentc_core.activity.models.content import SystemContent
from agentc_core.activity.models.content import UserContent
from agentc_core.activity.models.log import Log
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_testing.repo import ExampleRepoKind
from agentc_testing.repo import initialize_repo
from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory


@pytest.mark.smoke
def test_local_auditor_positive_1(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )

        # Note: flush is necessary for our tests, but this is not representative of a typical workflow.
        catalog = Catalog()
        global_span: GlobalSpan = catalog.Span(name="my project")
        logging_handler = global_span._local_logger.rotating_handler
        logging_handler.flush()

        # Test our global span logging.
        global_span.log(SystemContent(value="Hello world!"), my_annotation="my annotation")
        with (catalog.ActivityPath() / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            log_entry = Log.model_validate_json(fp.read())
            assert log_entry.span.name == ["my project"]
            assert log_entry.content.kind == "system"
            assert log_entry.content.value == "Hello world!"
            assert log_entry.catalog_version == catalog.version
            assert log_entry.annotations == {"my_annotation": "my annotation"}

        # Test nested span logging (level 1).
        level_1_span: Span = global_span.new(
            "my agent",
            my_annotation="my annotation",
            another_new_annotation="another new annotation",
            some_score=3,
        )
        level_1_span.log(
            KeyValueContent(key="key", value={"text": "Hello world again!"}), my_annotation="my new annotation"
        )
        logging_handler.flush()
        with (catalog.ActivityPath() / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # We are interested in the last line of the file.
            for i, line in enumerate(fp):  # noqa: B007
                pass

            assert i == 1
            log_entry = Log.model_validate_json(line)
            assert log_entry.span.name == ["my project", "my agent"]
            assert log_entry.content.kind == "key-value"
            assert log_entry.content.key == "key"
            assert log_entry.content.value["text"] == "Hello world again!"
            assert log_entry.catalog_version == catalog.version
            assert log_entry.annotations == {
                "my_annotation": "my new annotation",
                "another_new_annotation": "another new annotation",
                "some_score": 3,
            }

        # Test nested span logging (level 2).
        level_2_span: Span = level_1_span.new("my task", another_new_annotation="2")
        level_2_span.log(UserContent(value="Hello world once more!"), my_annotation="my newer annotation")
        logging_handler.flush()
        with (catalog.ActivityPath() / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            # We are interested in the last line of the file.
            for i, line in enumerate(fp):  # noqa: B007
                pass

            assert i == 2
            log_entry = Log.model_validate_json(line)
            assert log_entry.span.name == ["my project", "my agent", "my task"]
            assert log_entry.content.kind == "user"
            assert log_entry.content.value == "Hello world once more!"
            assert log_entry.catalog_version == catalog.version
            assert log_entry.annotations == {
                "my_annotation": "my newer annotation",
                "another_new_annotation": "2",
                "some_score": 3,
            }


@pytest.mark.smoke
def test_local_auditor_positive_2(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )

        # Note: flush is necessary for our tests, but this is not representative of a typical workflow.
        my_state = dict(messages=[])
        catalog = Catalog()
        global_span: GlobalSpan = catalog.Span(name="my project", state=my_state)
        logging_handler = global_span._local_logger.rotating_handler

        # Test our use of a context manager.
        with global_span:
            my_state["messages"].append("Hello world!")
        logging_handler.flush()

        # We expect two log messages.
        with (catalog.ActivityPath() / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            log_entry = Log.model_validate_json(fp.readline())
            assert log_entry.span.name == ["my project"]
            assert log_entry.content.kind == "begin"
            assert log_entry.content.state == dict(messages=[])
            assert log_entry.catalog_version == catalog.version
            log_entry = Log.model_validate_json(fp.readline())
            assert log_entry.span.name == ["my project"]
            assert log_entry.content.kind == "end"
            assert log_entry.content.state == dict(messages=["Hello world!"])
            assert log_entry.catalog_version == catalog.version


@pytest.mark.smoke
def test_local_auditor_positive_3(tmp_path):
    runner = click.testing.CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=click.testing.CliRunner(),
            click_command=click_main,
        )

        # Note: flush is necessary for our tests, but this is not representative of a typical workflow.
        catalog = Catalog()
        global_span: GlobalSpan = catalog.Span(name="my project")
        logging_handler = global_span._local_logger.rotating_handler

        # Test our use of the __setitem__ dunder.
        global_span["metric"] = 2
        logging_handler.flush()
        with (catalog.ActivityPath() / DEFAULT_ACTIVITY_FILE).open("r") as fp:
            log_entry = Log.model_validate_json(fp.readline())
            assert log_entry.span.name == ["my project"]
            assert log_entry.content.kind == "key-value"
            assert log_entry.content.key == "metric"
            assert log_entry.content.value == 2


@pytest.mark.skip
@pytest.mark.slow
def test_db_auditor(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.slow
def test_chain_auditor(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass
