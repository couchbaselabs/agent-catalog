import click.testing
import enum
import git
import logging
import os
import pathlib
import shutil

logger = logging.getLogger(__name__)

# TODO (GLENN): We should move this to a more appropriate location.
os.environ["AGENT_CATALOG_DEBUG"] = "true"


class ExampleRepoKind(enum.StrEnum):
    EMPTY = "empty"

    # The following relate to different travel-agent tests.
    NON_INDEXED_ALL_TRAVEL = "non_indexed_clean_all_travel"
    INDEXED_CLEAN_ALL_TRAVEL = "indexed_clean_all_travel"
    INDEXED_DIRTY_ALL_TRAVEL = "indexed_dirty_all_travel"
    PUBLISHED_ALL_TRAVEL = "published_all_travel"

    # The following relate to different tool/prompt only tests.
    INDEXED_CLEAN_TOOLS_TRAVEL = "indexed_clean_tools_travel"
    INDEXED_CLEAN_INPUTS_TRAVEL = "indexed_clean_inputs_travel"
    PUBLISHED_TOOLS_TRAVEL = "published_tools_travel"
    PUBLISHED_INPUTS_TRAVEL = "published_inputs_travel"


def initialize_repo(
    directory: pathlib.Path,
    repo_kind: ExampleRepoKind,
    click_runner: click.testing.CliRunner,
    click_command: click.Command,
    index_args: list = None,
    publish_args: list = None,
) -> list[click.testing.Result]:
    repo: git.Repo = git.Repo.init(directory)
    with (directory / "README.md").open("w") as f:
        f.write("# Test Test\nI'm a test!")

    # For all tests, we will use a sentence-transformers model saved in the agentc_testing module.
    os.environ["AGENT_CATALOG_SENTENCE_TRANSFORMERS_MODEL_CACHE"] = str(
        (pathlib.Path(__file__).parent / "resources" / "models").absolute()
    )

    # Depending on the repo kind, copy the appropriate files to the input directory.
    files_to_commit = ["README.md"]
    match repo_kind:
        case ExampleRepoKind.EMPTY:
            pass

        case ExampleRepoKind.NON_INDEXED_ALL_TRAVEL | ExampleRepoKind.INDEXED_DIRTY_ALL_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)

        case ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL | ExampleRepoKind.PUBLISHED_ALL_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in travel_agent_path.rglob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL | ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in (travel_agent_path / "tools").glob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case ExampleRepoKind.INDEXED_CLEAN_INPUTS_TRAVEL | ExampleRepoKind.PUBLISHED_INPUTS_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in (travel_agent_path / "inputs").glob("*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case _:
            raise ValueError(f"Unknown repo kind encountered: {repo_kind}")

    # Commit our files.
    repo.index.add(files_to_commit)
    repo.index.commit("Initial commit")
    output = list()

    # If we are not using the index command, we can return early...
    if repo_kind == ExampleRepoKind.EMPTY or repo_kind == ExampleRepoKind.NON_INDEXED_ALL_TRAVEL:
        return output

    # ...otherwise we need to initialize our catalog...
    output.append(click_runner.invoke(click_command, ["init", "catalog", "--local", "--no-db"]))

    # ...and, call the index command.
    os.environ["AGENT_CATALOG_BUCKET"] = "travel-sample"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    if repo_kind not in [ExampleRepoKind.INDEXED_CLEAN_INPUTS_TRAVEL, ExampleRepoKind.PUBLISHED_INPUTS_TRAVEL]:
        output.append(click_runner.invoke(click_command, ["index", "tools", "--no-model-inputs"] + (index_args or [])))
    if repo_kind not in [ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL, ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL]:
        output.append(click_runner.invoke(click_command, ["index", "inputs", "--no-tools"] + (index_args or [])))
    if repo_kind not in [
        ExampleRepoKind.PUBLISHED_ALL_TRAVEL,
        ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL,
        ExampleRepoKind.PUBLISHED_INPUTS_TRAVEL,
    ]:
        return output

    # Initialize the DB catalog.
    output.append(click_runner.invoke(click_command, ["init", "catalog", "--no-local", "--db"]))

    # Call our publish command. Note that this assumes a container / CB instance is active!
    os.environ["AGENT_CATALOG_MAX_INDEX_PARTITION"] = "1"
    os.environ["AGENT_CATALOG_INDEX_PARTITION"] = "1"
    if repo_kind != ExampleRepoKind.PUBLISHED_INPUTS_TRAVEL:
        output.append(
            click_runner.invoke(click_command, ["publish", "tool", "--bucket", "travel-sample"] + (publish_args or []))
        )
    if repo_kind != ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL:
        output.append(
            click_runner.invoke(
                click_command, ["publish", "model-input", "--bucket", "travel-sample"] + (publish_args or [])
            )
        )
    logger.info(output)
    return output


if __name__ == "__main__":
    # Note: agentc_testing should never have an explicit dependency on agentc_cli!
    from agentc_cli.main import click_main as _click_main

    _runner = click.testing.CliRunner()
    with _runner.isolated_filesystem() as td:
        _results = initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.PUBLISHED_ALL_TRAVEL,
            click_runner=_runner,
            click_command=_click_main,
        )
        print(_results)
