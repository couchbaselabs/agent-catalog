# agentc-core

The core for the Couchbase Agent Catalog project.

## Building From Source

Ensure that you have installed dependencies as mentioned in the [agentc_core/README.md](README.md).

You should now have the `agentc` command line tool installed.
Run the `agentc` command to test your installation.

   ```bash
   agentc
   # or agentc --help
   ```

   ```
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

     A command line tool for AGENT_CATALOG.

   Options:
     -c, --catalog DIRECTORY   Directory of local catalog files. The local catalog DIRECTORY should be checked into git.  [default: .agent-catalog]
     -a, --activity DIRECTORY  Directory of local activity files (runtime data). The local activity DIRECTORY should NOT be checked into git, as it holds runtime activity data like logs, etc.  [default: .agent-activity]
     -v, --verbose             Enable verbose output.
     --help                    Show this message and exit.

   Commands:
     clean    Clean up the catalog folder, the activity folder, any generated files, etc.
     env      Show agentc's environment or configuration parameters as a JSON object.
     execute  Execute specific tool to test it with an agent.
     find     Find items from the catalog based on a natural language QUERY string.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     publish  Publish the local catalog to Couchbase DB.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com for more information.
   ```

For examples on what an agentic workflow with `agentc` looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=1
```

## For Developers

### Setting up Pre-Commit

To set up `pre-commit` and reap all the benefits of code formatting, linting, automatic `poetry` lock generation, etc...
execute the following command:

```bash
pip install pre-commit
pre-commit install
```

### Working with Poetry

Below, we list out some notes that developers might find useful w.r.t. Poetry:

1. Before committing, always use `poetry update; poetry lock`!
   This will check if the dependencies laid out in the `pyproject.toml` file are satisfiable and will repopulate the
   lock file appropriately.
2. `poetry install` vs. `poetry update`: in the presence of a `poetry.lock` file (which we do have), the former will
   only consider installing packages specified in the lock file.
   The latter (`poetry update`) will read from the `pyproject.toml` file and try to resolve dependencies from there.
3. Because these are a collection of libraries, we will not commit individual lock files for each sub-package. **Do not
   commit `poetry.lock` files.**