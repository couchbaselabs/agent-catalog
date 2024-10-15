# agent-catalog

The mono-repo for the Couchbase Agent Catalog project.

## Docs and Templates

Refer to [`docs/`](docs) to explore templates and other references while writing your agent workflow with Couchbase
Agent Catalog.

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

To set up `pre-commit` and reap all the benefits of code formatting, linting, etc...
execute the following command:

```bash
pip install pre-commit
pre-commit install
```

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=1
```

