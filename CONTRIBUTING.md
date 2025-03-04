# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.
_This README is intended for all `agent-catalog` contributors._

## Table of Contents
- [On Packages (inside `libs`)](#on-packages-inside-libs)
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
4. [`agentc-integrations`](libs/agentc_integrations/), which contains additional tooling around building both
   LangChain-specific (`libs/agentc_integrations/langchain`) and LlamaIndex-specific
   (`libs/agentc_integrations/llamaindex`) agents.

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

## Setting up Pre-Commit

To set up `pre-commit` and reap all the benefits of code formatting, linting, etc... execute the following command:

```bash
pre-commit install
```

## Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=true
```

## Running Tests (Pytest)

To run the entire suite of unit tests, use the following `pytest` command in the project root:

```bash
pytest --log-file .output --log-level DEBUG
```

This command will a) run all tests in the current working directory, b) record the logger output to a `.output` file,
and c) set the logging level to DEBUG.

To only run smoke tests, use the following `pytest` command (again, from the project root):

```bash
pytest -m smoke --log-file .output --log-level DEBUG
```

To run tests for a specific package, use the following `pytest` command (again, from the project root):

```bash
pytest libs/agentc_core --log-file .output --log-level DEBUG
```

Note that Click doesn't play too well with pytest's `log_cli=true` option, so we recommend logging to a file.
For more information about our command line tool, see
[here](https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags).
