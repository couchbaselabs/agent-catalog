# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.

## Table of Contents
- [Getting Started](#getting-started)
  * [Installing from Package](#installing-from-package)
  * [Installing from Source (with Pip)](#installing-from-source-with-pip)
  * [Installing from Source (with Poetry)](#installing-from-source-with-poetry)
  * [Verifying Your Installation](#verifying-your-installation)
- [Building From Source](#building-from-source)
- [Docs and Templates](#docs-and-templates)
- [For Contributors / Developers](#for-contributors--developers)
  * [On Packages (inside `libs`)](#on-packages-inside-libs)
  * [Working with Poetry](#working-with-poetry)
  * [Setting up Pre-Commit](#setting-up-pre-commit)
  * [Enabling Debug Mode](#enabling-debug-mode)

## Getting Started

### Installing from Package

(in the works!)

### Installing from Source (with Pip)

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!

2. Clone this repository.

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   ```

3. Installation using Makefile

   To run the following `make` commands, you must have Anaconda and Make installed (`make` for [MacOS](https://formulae.brew.sh/formula/make), [Windows](https://gnuwin32.sourceforge.net/packages/make.htm), [Ubuntu](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/)).


   We recommend using Anaconda to create a virtual environment for your project to ensure no global dependencies interfere with the project.

   [Click here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) for Anaconda installation steps.

   Once anaconda or any of its distribution is installed, run the following commands to create and activate a virtual environment using Anaconda and install Agentc.
   Replace `agentcenv` with any other suitable environment name.
   ```bash
   make dev-local-pip env_name=agentcenv
   conda activate agentcenv
   ```

   You are now ready to explore Agentc!

4. Manual Installation

   Alternatively, you can choose to manually install Agentc by first creating a virtual environment either using Anaconda or any other Python virtual environment manager.
   ```bash
   # create venv using Anaconda
   conda create -n agentcenv python=3.12
   conda activate agentcenv
   ```

   Once environment is set up, execute the following command to install a local package with `pip`:
   ```bash
   cd agent-catalog
   # Install the agentc package.
   pip install libs/agentc
   ```

   If you are interested in developing with langchain, also install `agentc_langchain` by running the following:

   ```bash
   pip install libs/agentc_langchain
   ```

   If you are interested in building a ``.whl`` file (for later use in ``.whl``-based installs), use :command:`poetry`
   directly:

   ```bash
   cd libs/agentc
   poetry build
   ```

### Installing from Source (with Poetry)

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!

2. Clone this repository.

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   ```

3. Within *your own* `pyproject.toml` file, add the following dependency to your project:
   The `path` should point to the location of the `agentc` package (and is relative to the `pyproject.toml`
   file itself).

   ```toml
   [tool.poetry.dependencies]
   agentc = { path = "agent-catalog/libs/agentc", develop = true }
   ```

4. Run the command `poetry update` to install the Agent Catalog package.

   ```bash
   cd agent-catalog
   poetry update
   ```

5. Install using Makefile

   You can install Agentc without adding to your pyproject if you wish to explore first. Simply run the following make commands to create and activate a virtual environment and install the requirements.

   To run the following `make` commands, you must have Anaconda and Make installed (`make` for [MacOS](https://formulae.brew.sh/formula/make), [Windows](https://gnuwin32.sourceforge.net/packages/make.htm), [Ubuntu](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/)).

   We recommend using Anaconda to create a virtual environment for your project to ensure no global dependencies interfere with the project.

   [Click here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) for Anaconda installation steps.

   Once anaconda or any of its distribution is installed, run the following commands to create and activate a virtual environment using Anaconda and install Agentc.
   Replace `agentcenv` with any other suitable environment name.

   ```bash
   make dev-local-poetry env_name=agentcenv
   conda activate agentcenv
   ```

### Verifying Your Installation

If you've followed the steps above, you should now have the `agentc` command line tool.
Run `agentc --help` to verify your installation (note that your first run will take a couple of seconds as some
libraries like numpy need to be built, subsequent runs will be faster).

```bash
Usage: agentc [OPTIONS] COMMAND [ARGS]...

  The Couchbase Agent Catalog command line tool.

Options:
  -c, --catalog DIRECTORY         Directory of the local catalog files.  [default: .agent-catalog]
  -a, --activity DIRECTORY        Directory of the local activity files (runtime data).  [default: .agent-activity]
  -v, --verbose                   Flag to enable verbose output.  [default: 0; 0<=x<=2]
  -i, --interactive / -ni, --no-interactive
                                  Flag to enable interactive mode.  [default: i]
  --help                          Show this message and exit.

Commands:
  add      Interactively create a new tool or prompt and save it to the filesystem (output).
  clean    Delete all or specific (catalog and/or activity) agent related files / collections.
  env      Return all agentc related environment and configuration parameters as a JSON object.
  execute  Search and execute a specific tool.
  find     Find items from the catalog based on a natural language QUERY string or by name.
  index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
  ls       List all indexed tools and/or prompts in the catalog.
  publish  Upload the local catalog and/or logs to a Couchbase instance.
  status   Show the status of the local catalog.
  version  Show the current version of agentc.

  See: https://docs.couchbase.com or https://couchbaselabs.github.io/agent-catalog/index.html# for more information.
```

If you see the output above, you are all set! Head on over to our [docs](https://couchbaselabs.github.io/agent-catalog/) or our [templates](templates) to start
developing your agent with Agent Catalog.

## Building From Source

For examples on what an agentic workflow with `agentc` looks like, see
the [agent-catalog-example](https://github.com/couchbaselabs/agent-catalog-example) repository.

## Adding files to ignore while indexing

By default, the `index` command will ignore files/patterns present in `.gitignore` file.
In addition to `.gitignore`, there might be situation where additional files have to be ignored by agentc and not git.
To add such files/pattern `.agentcignore` file can be used similar to `.gitignore`.

For more guide on how to use `.agentcignore` file check the [documentation](https://couchbaselabs.github.io/agent-catalog/guide.html#ignoring-files-while-indexing)

## Docs and Templates

Refer to [`docs/`](docs) to explore templates and other references while writing your agent workflow with Couchbase
Agent Catalog. We also provide some starter [`recipes`](templates) if you are building an agent from scratch.

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
pip install pre-commit
pre-commit install
```

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=1
```

