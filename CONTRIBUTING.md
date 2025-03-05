# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.
_This README is intended for all `agent-catalog` contributors._

## Table of Contents

- [On Packages (inside `libs`)](#on-packages-inside-libs)
- [How to Contribute](#how-to-contribute)
- [Working with Poetry](#working-with-poetry)
- [Setting up Pre-Commit](#setting-up-pre-commit)
- [Enabling Debug Mode](#enabling-debug-mode)
- [Running Tests (Pytest)](#running-tests-pytest)

## On Packages (inside `libs`)

Every project package is wrapped under [`libs`](libs).
The following are sub-folders that you can explore:

1. [`agentc`](libs/agentc), which contains the front-facing package for the Couchbase Agent Catalog project.
2. [`agentc-cli`](libs/agentc_cli), which contains the command line interface for the Couchbase Agent Catalog project.
3. [`agentc-core`](libs/agentc_core), which contains the core SDK package for the Couchbase Agent Catalog project.
4. [`agentc-integrations`](libs/agentc_integrations), which contains additional tooling around building both
   LangChain-specific (`libs/agentc_integrations/langchain`) and LlamaIndex-specific
   (`libs/agentc_integrations/llamaindex`) agents.

## How to Contribute

Our current process for contributors is as follows:

1. Set up your local development environment!
   This involves a) cloning this repository, b) setting up a virtual Python environment, and c) building this repository
   with Poetry (we offer a Makefile to help expedite the latter two steps).

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   make setup

   # Activate your environment.
   eval $(poetry env activate)
   ```

2. Load our pre-commit hooks into your local repository.
   `pre-commit` will take of code formatting and linting on `git commit`.
   If your code fails the pre-commit steps, `pre-commit` will reject the commit (and attempt to correct the violations
   if possible).
   Note that `pre-commit` is also run by the `tests.yaml` workflow (whose success enables rebase with the main branch),
   so running `pre-commit` locally is meant to save you time:

   ```bash
   pre-commit install
   ```

3. In your local repository, create a new branch whose name is `$USER/$TITLE_OF_PR` (where `$USER` is your
   username and `$TITLE_OF_PR` is a short title describing your change).

   ```bash
   git checkout -b $USER/$TITLE_OF_PR
   ```

4. Add (`git commit`) your changes with tests where appropriate.
   We use Pytest markers to identify two sets of tests: `smoke` and `slow`.
   `smoke` tests are those that don't require a Couchbase instance (i.e., local-only operations), with all other tests
   falling into `slow`.
   To run `smoke` tests and quickly test your changes, run the following command in the project root:

   ```bash
   # eval $(poetry env activate)
   pytest . -m smoke
   ```

   Before pushing your change (if you don't want to rely on using the `tests.yaml` workflow), you can run all tests
   locally with the command below in the project root:

   ```bash
   # eval $(poetry env activate)
   pytest .
   ```

5. Ensure all of your changes are commited, and push your changes to Github.

   ```bash
   git add $MODIFIED_FILES
   git commit
   git push
   ```

6. You should now see your branch on Github.
   On Github, create a pull request (Pull Requests -> New Pull Request -> Create Pull Request).

   TODO (GLENN): Finish this...

   Wait for all tests in `tests.yaml` to pass b

## Working with Poetry

Below, we list out some notes that developers might find useful w.r.t. Poetry:

1. Before committing, always use `poetry update; poetry lock`!
   This will check if the dependencies laid out in the `pyproject.toml` file are satisfiable and will repopulate the
   lock file appropriately.

2. `poetry install` vs. `poetry update`: in the presence of a `poetry.lock` file (which we do have), the former will
   only consider installing packages specified in the lock file.
   The latter (`poetry update`) will read from the `pyproject.toml` file and try to resolve dependencies from there.

3. Because these are a collection of libraries, we do not commit individual lock files for each sub-package.
   **Do not commit `poetry.lock` files.**

## Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=true
```

## Running Tests (Pytest)

To run the entire suite of unit tests, use the following `pytest` command in the project root:

```bash
pytest . --log-file .output --log-level DEBUG
```

This command will a) run all tests in the current working directory, b) record the logger output to a `.output` file,
and c) set the logging level to DEBUG.

To only run smoke tests, use the following `pytest` command (again, from the project root):

```bash
pytest . -m smoke --log-file .output --log-level DEBUG
```

To run tests for a specific package, use the following `pytest` command (again, from the project root):

```bash
pytest libs/agentc_core --log-file .output --log-level DEBUG
```

Note that Click doesn't play too well with pytest's `log_cli=true` option, so we recommend logging to a file.
For more information about Pytest's command line tool, see
[here](https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags).
