import click.testing
import dataclasses
import enum
import git
import logging
import os
import pathlib
import pytest
import shutil
import typing

logger = logging.getLogger(__name__)

# TODO (GLENN): We should move this to a more appropriate location.
os.environ["AGENT_CATALOG_DEBUG"] = "true"


class EnvironmentKind(enum.StrEnum):
    EMPTY = "empty"

    # The following relate to different travel-agent tests.
    NON_INDEXED_ALL_TRAVEL = "non_indexed_clean_all_travel"
    INDEXED_CLEAN_ALL_TRAVEL = "indexed_clean_all_travel"
    INDEXED_DIRTY_ALL_TRAVEL = "indexed_dirty_all_travel"
    PUBLISHED_ALL_TRAVEL = "published_all_travel"

    # The following relate to different tool/prompt only tests.
    INDEXED_CLEAN_TOOLS_TRAVEL = "indexed_clean_tools_travel"
    INDEXED_CLEAN_PROMPTS_TRAVEL = "indexed_clean_prompts_travel"
    PUBLISHED_TOOLS_TRAVEL = "published_tools_travel"
    PUBLISHED_PROMPTS_TRAVEL = "published_prompts_travel"


@dataclasses.dataclass
class Environment:
    build_results: list[click.testing.Result]
    repository: git.Repo


def _initialize_git(
    directory: pathlib.Path,
    env_kind: EnvironmentKind,
    repo: git.Repo,
):
    # Depending on the repo kind, copy the appropriate files to the input directory.
    files_to_commit = ["README.md"]
    match env_kind:
        case EnvironmentKind.EMPTY:
            pass

        case EnvironmentKind.NON_INDEXED_ALL_TRAVEL | EnvironmentKind.INDEXED_DIRTY_ALL_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)

        case EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL | EnvironmentKind.PUBLISHED_ALL_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in travel_agent_path.rglob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL | EnvironmentKind.PUBLISHED_TOOLS_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in (travel_agent_path / "tools").glob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case EnvironmentKind.INDEXED_CLEAN_PROMPTS_TRAVEL | EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in (travel_agent_path / "prompts").glob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case _:
            raise ValueError(f"Unknown repo kind encountered: {env_kind}")

    # Commit our files.
    repo.index.add(files_to_commit)
    repo.index.commit("Initial commit")
    if env_kind == EnvironmentKind.INDEXED_DIRTY_ALL_TRAVEL:
        with (directory / "README.md").open("a") as f:
            f.write("\nI'm dirty now!")
        assert repo.is_dirty()


def _initialize_catalog(
    env_kind: EnvironmentKind, click_runner: click.testing.CliRunner, click_command: click.Command, *args
):
    output = list()
    match env_kind:
        case (
            EnvironmentKind.NON_INDEXED_ALL_TRAVEL
            | EnvironmentKind.INDEXED_DIRTY_ALL_TRAVEL
            | EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL
            | EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL
            | EnvironmentKind.INDEXED_CLEAN_PROMPTS_TRAVEL
        ):
            output.append(click_runner.invoke(click_command, ["init", "catalog", "--local", "--no-db"] + list(args)))
            output.append(click_runner.invoke(click_command, ["init", "activity", "--local", "--no-db"] + list(args)))

        case (
            EnvironmentKind.PUBLISHED_ALL_TRAVEL
            | EnvironmentKind.PUBLISHED_TOOLS_TRAVEL
            | EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL
        ):
            output.append(click_runner.invoke(click_command, ["init", "catalog", "--local", "--db"] + list(args)))
            output.append(click_runner.invoke(click_command, ["init", "activity", "--local", "--db"] + list(args)))

        case _:
            # We should not reach here.
            raise ValueError(f"Cannot handle the env_kind '{env_kind}' at this point!")

    return output


def _index_catalog(
    env_kind: EnvironmentKind, click_runner: click.testing.CliRunner, click_command: click.Command, *args
):
    output = list()
    match env_kind:
        case EnvironmentKind.INDEXED_CLEAN_PROMPTS_TRAVEL | EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL:
            output.append(click_runner.invoke(click_command, ["index", "prompts", "--no-tools"] + list(args)))
        case EnvironmentKind.INDEXED_CLEAN_TOOLS_TRAVEL | EnvironmentKind.PUBLISHED_TOOLS_TRAVEL:
            output.append(click_runner.invoke(click_command, ["index", "tools", "--no-prompts"] + list(args)))
        case (
            EnvironmentKind.INDEXED_DIRTY_ALL_TRAVEL
            | EnvironmentKind.INDEXED_CLEAN_ALL_TRAVEL
            | EnvironmentKind.PUBLISHED_ALL_TRAVEL
        ):
            output.append(click_runner.invoke(click_command, ["index", "tools", "prompts"] + list(args)))
        case _:
            # We should not reach here.
            raise ValueError(f"Cannot handle the env_kind '{env_kind}' at this point!")
    return output


def _publish_catalog(
    env_kind: EnvironmentKind, click_runner: click.testing.CliRunner, click_command: click.Command, *args
):
    os.environ["AGENT_CATALOG_MAX_INDEX_PARTITION"] = "1"
    os.environ["AGENT_CATALOG_INDEX_PARTITION"] = "1"
    output = list()
    match env_kind:
        case EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL:
            output.append(click_runner.invoke(click_command, ["publish", "prompts"] + list(args)))
        case EnvironmentKind.PUBLISHED_TOOLS_TRAVEL:
            output.append(click_runner.invoke(click_command, ["publish", "tools"] + list(args)))
        case EnvironmentKind.PUBLISHED_ALL_TRAVEL:
            output.append(click_runner.invoke(click_command, ["publish"] + list(args)))
        case _:
            # We should not reach here.
            raise ValueError(f"Cannot handle the env_kind '{env_kind}' at this point!")
    return output


def _build_environment(
    repo: git.Repo,
    directory: pathlib.Path,
    env_kind: EnvironmentKind,
    click_runner: click.testing.CliRunner,
    click_command: click.Command,
    init_args: list = None,
    index_args: list = None,
    publish_args: list = None,
) -> Environment:
    logger.info("Building environment with kind: %s.", env_kind)
    if init_args is None:
        init_args = list()
    if index_args is None:
        index_args = list()
    if publish_args is None:
        publish_args = list()

    # Create a new git repo in the directory.
    os.chdir(directory)
    with (directory / "README.md").open("w") as f:
        f.write("# Test Test\nI'm a test!")

    # For all tests, we will use a sentence-transformers model saved in the agentc_testing module.
    os.environ["AGENT_CATALOG_SENTENCE_TRANSFORMERS_MODEL_CACHE"] = str(
        (pathlib.Path(__file__).parent / "resources" / "models").absolute()
    )
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    # Initialize the git repository.
    _initialize_git(directory, env_kind, repo)

    # If we are not using the index command, we can return early...
    build_results = list()
    if env_kind == EnvironmentKind.EMPTY:
        logger.info(f"{env_kind}: %s", build_results)
        return Environment(build_results=build_results, repository=repo)

    # ...otherwise we need to initialize our catalog...
    build_results.append(_initialize_catalog(env_kind, click_runner, click_command, *init_args))
    if env_kind == EnvironmentKind.NON_INDEXED_ALL_TRAVEL:
        logger.info(f"{env_kind}: %s", build_results)
        return Environment(build_results=build_results, repository=repo)

    # ...and, call the index command.
    build_results.append(_index_catalog(env_kind, click_runner, click_command, *index_args))
    if env_kind not in [
        EnvironmentKind.PUBLISHED_ALL_TRAVEL,
        EnvironmentKind.PUBLISHED_TOOLS_TRAVEL,
        EnvironmentKind.PUBLISHED_PROMPTS_TRAVEL,
    ]:
        logger.info(f"{env_kind}: %s", build_results)
        return Environment(build_results=build_results, repository=repo)

    # Call our publish command. Note that this assumes a container / CB instance is active!
    build_results.append(_publish_catalog(env_kind, click_runner, click_command, *publish_args))
    logger.info(f"{env_kind}: %s", build_results)
    return Environment(build_results=build_results, repository=repo)


@pytest.fixture
def environment_factory() -> typing.Callable[..., Environment]:
    repository_instance: list[git.Repo] = list()
    directory_instance: list[pathlib.Path] = list()
    try:
        # We need to capture the environment we spawn.
        def get_environment(
            directory: pathlib.Path,
            env_kind: EnvironmentKind,
            click_runner: click.testing.CliRunner,
            click_command: click.Command,
            init_args: list = None,
            index_args: list = None,
            publish_args: list = None,
        ) -> Environment:
            _repository = git.Repo.init(directory)
            repository_instance.append(_repository)
            directory_instance.append(directory)
            return _build_environment(
                directory=directory,
                repo=_repository,
                env_kind=env_kind,
                click_runner=click_runner,
                click_command=click_command,
                init_args=init_args,
                index_args=index_args,
                publish_args=publish_args,
            )

        # Enter our test.
        yield get_environment

    finally:
        # Clean up the environment.
        if repository_instance:
            repository_instance.pop().close()
        if directory_instance:
            shutil.rmtree(directory_instance.pop(), ignore_errors=True)


if __name__ == "__main__":
    # Note: agentc_testing should never have an explicit dependency on agentc_cli!
    from agentc_cli.main import click_main as _click_main

    _runner = click.testing.CliRunner()
    with _runner.isolated_filesystem() as td:
        _results = _build_environment(
            directory=pathlib.Path(td),
            repo=git.Repo.init(pathlib.Path(td)),
            env_kind=EnvironmentKind.PUBLISHED_ALL_TRAVEL,
            click_runner=_runner,
            click_command=_click_main,
        )
        print(_results)
