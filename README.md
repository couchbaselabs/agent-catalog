# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.

## Table of Contents

- [Getting Started](#getting-started)
    * [Installing from Package](#installing-from-package)
    * [Installing from Source (with Makefile)](#installing-from-source-with-makefile)
    * [Installing from Source (with Poetry)](#installing-from-source-with-poetry)
- [Docs and Templates](#docs-and-templates)
- [For Contributors / Developers](#for-contributors--developers)
    * [On Packages (inside `libs`)](#on-packages-inside-libs)
    * [Working with Poetry](#working-with-poetry)
    * [Setting up Pre-Commit](#setting-up-pre-commit)
    * [Enabling Debug Mode](#enabling-debug-mode)

## Getting Started

### Installing from Package

(in the works!)

### Installing from Source (with Makefile)

1. Make sure you have `python3.12` and [`poetry`](https://python-poetry.org/docs/#installation) installed!

2. Make sure you have `make` installed!
   For Mac-based installations, see [here](https://formulae.brew.sh/formula/make).
   For Windows-based installations, see [here](https://gnuwin32.sourceforge.net/packages/make.htm).
   For Ubuntu-based installations, see [here](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/).

3. Clone this repository.

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   ```

4. Navigate to the `agent-catalog` directory and run `make`.
   This will a) create a new virtual environment using Poetry and b) install all required packages and CLI tools.

6. Activate your newly created virtual environment using the outputs of `make activate` or `poetry env activate`.
   If you do not want to copy-and-paste the output, you can run the command with `eval`:

   ```bash
   eval $(poetry env activate)
   ```

   If your environment has been successfully activated, you should see `(Activated)` after running `poetry env list`...
   ```bash
   poetry env list
   > agent-catalog-UEfqTvAT-py3.13 (Activated)
   ```

   ...**and** you should see that your `python` now points to the python in your virtual environment (not your system
   default).
   ```bash
   which python
   > /Users/....../Library/Caches/pypoetry/virtualenvs/agent-catalog-UEfqTvAT-py3.13/bin/python
   ```

6. If you are interested in building a `.whl` file (for later use in `.whl`-based installation in other projects),
   run the following command:

   ```bash
   cd libs/agentc
   poetry build
   ```

### Installing from Source (with Anaconda)

1. Make sure you have `python3.12` and
   [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) installed!

2. Create a new virtual environment with Anaconda and subsequently activate your environment.
   Again, you must activate your environment before running any `agentc` commands!
   ```bash
   conda create -n my_agentc_env python=3.12
   conda activate my_agentc_env
   ```

3. Navigate to this directory and install Agent Catalog with `pip`:
   ```bash
   cd agent-catalog

   # Install the agentc package.
   pip install libs/agentc
   ```

   If you are interested in developing with LangChain or LangGraph, install the helper `agentc_langchain` package with
   the command below:
   ```bash
   pip install libs/agentc_langchain
   ```

## Docs and Templates

Refer to [`docs/`](docs) to build our technical documentation
(also hosted [here](https://couchbaselabs.github.io/agent-catalog/index.html) and explore Couchbase Agent Catalog
before authoring your agent applications.
We also provide some starter [`agents`](templates/agents) using different frameworks to understand the flow better.

For more info on basic tool and prompt definitions, please refer to the [`tool`](templates/tools) and
[`prompt`](templates/prompts) templates that can be created using `agentc add` command.

## For Contributors / Developers

### On Packages (inside `libs`)

Every project package is wrapped under [`libs`](libs). The following are sub-folders that you can explore:

1. [`agentc`](libs/agentc), which contains the front-facing package for the Couchbase Agent Catalog project.
2. [`agentc-cli`](libs/agentc_cli), which contains the command line interface for the Couchbase Agent Catalog project.
3. [`agentc-core`](libs/agentc_core), which contains the core SDK package for the Couchbase Agent Catalog project.
4. [`agentc-langchain`](libs/agentc_langchain), which contains additional tooling around building LangChain-specific
   agents.

### Working with Poetry

Below, we list out some notes that developers might find useful w.r.t. Poetry:

1. Before committing, always use `poetry update; poetry lock`!
   This will check if the dependencies laid out in the `pyproject.toml` file are satisfiable and will repopulate the
   lock file appropriately.
2. `poetry install` vs. `poetry update`: in the presence of a `poetry.lock` file (which we do have), the former will
   only consider installing packages specified in the lock file.
   The latter (`poetry update`) will read from the `pyproject.toml` file and try to resolve dependencies from there.
3. Because these are a collection of libraries, we do not commit individual lock files for each sub-package. **Do not
   commit `poetry.lock` files.**

### Setting up Pre-Commit

To set up `pre-commit` and reap all the benefits of code formatting, linting, etc... execute the following command:

```bash
pre-commit install
```

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=true
```

### Running Tests

To run any of the unit tests authored in `libs/agentc*/test`, use the following `pytest` command:

```bash
pytest libs/agentc_cli/tests libs/agentc_core/tests --log-file .output
```

This command will run all tests and record the logger output to a `.output` file.
Note that Click doesn't play too well with pytest's `log_cli=true` option, so we recommend logging to a file.
