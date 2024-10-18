# agentc-core

The core for the Couchbase Agent Catalog project.

## Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=1
```

## Setting up Pre-Commit

To set up `pre-commit` and reap all the benefits of code formatting, linting, automatic `poetry` lock generation, etc...
execute the following command:

```bash
pip install pre-commit
pre-commit install
```

## Working with Poetry

Below, we list out some notes that developers might find useful w.r.t. Poetry:

1. Before committing, always use `poetry update; poetry lock`!
   This will check if the dependencies laid out in the `pyproject.toml` file are satisfiable and will repopulate the
   lock file appropriately.
2. `poetry install` vs. `poetry update`: in the presence of a `poetry.lock` file (which we do have), the former will
   only consider installing packages specified in the lock file.
   The latter (`poetry update`) will read from the `pyproject.toml` file and try to resolve dependencies from there.
3. Because these are a collection of libraries, we will not commit individual lock files for each sub-package. **Do not
   commit `poetry.lock` files.**