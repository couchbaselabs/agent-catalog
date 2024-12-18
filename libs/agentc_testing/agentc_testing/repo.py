import click.testing
import enum
import git
import os
import pathlib
import shutil


class ExampleRepoKind(enum.StrEnum):
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
            for filename in travel_agent_path.rglob("*tools*"):
                if filename.is_file():
                    files_to_commit.append(filename.relative_to(travel_agent_path))

        case ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL | ExampleRepoKind.PUBLISHED_PROMPTS_TRAVEL:
            travel_agent_path = pathlib.Path(__file__).parent / "resources" / "travel_agent"
            shutil.copytree(travel_agent_path.absolute(), directory.absolute(), dirs_exist_ok=True)
            for filename in travel_agent_path.rglob("*prompts*"):
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

    # ...otherwise, we'll call the index command.
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    if repo_kind not in [ExampleRepoKind.INDEXED_CLEAN_PROMPTS_TRAVEL, ExampleRepoKind.PUBLISHED_PROMPTS_TRAVEL]:
        output.append(click_runner.invoke(click_command, ["index", "tools", "--no-prompts"] + (index_args or [])))
    if repo_kind not in [ExampleRepoKind.INDEXED_CLEAN_TOOLS_TRAVEL, ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL]:
        output.append(click_runner.invoke(click_command, ["index", "prompts", "--no-tools"] + (index_args or [])))
    if repo_kind not in [
        ExampleRepoKind.PUBLISHED_ALL_TRAVEL,
        ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL,
        ExampleRepoKind.PUBLISHED_PROMPTS_TRAVEL,
    ]:
        return output

    # Call our publish command. Note that this assumes a container / CB instance is active!
    os.environ["AGENT_CATALOG_MAX_SOURCE_PARTITION"] = "1"
    os.environ["AGENT_CATALOG_INDEX_PARTITION"] = "1"
    if repo_kind != ExampleRepoKind.PUBLISHED_PROMPTS_TRAVEL:
        output.append(
            click_runner.invoke(click_command, ["publish", "tool", "--bucket", "travel-sample"] + (publish_args or []))
        )
    if repo_kind != ExampleRepoKind.PUBLISHED_TOOLS_TRAVEL:
        output.append(
            click_runner.invoke(
                click_command, ["publish", "prompt", "--bucket", "travel-sample"] + (publish_args or [])
            )
        )
    print(output)
    return output


if __name__ == "__main__":
    # Note: agentc_testing should never have an explicit dependency on agentc_cli!
    from agentc_cli.main import click_main as _click_main

    _runner = click.testing.CliRunner()
    with _runner.isolated_filesystem() as td:
        _results = initialize_repo(
            directory=pathlib.Path(td),
            repo_kind=ExampleRepoKind.INDEXED_CLEAN_ALL_TRAVEL,
            click_runner=_runner,
            click_command=_click_main,
        )
        print(_results)
