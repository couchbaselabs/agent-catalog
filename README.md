# agent-catalog

The mono-repo for the Couchbase Agent Catalog project.

## Getting Started

### Installing from Package

(in the works!)

### Installing from Source

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Clone this repository. Make sure you have your SSH key setup!

   ```bash
   git clone git@github.com:couchbaselabs/agent-catalog.git
   ```

3. Build the `agentc` package using Poetry.

   ```bash
   cd libs/agentc
   poetry build
   ```

4. You should now have a `dist` folder inside `libs/agentc` populated with a `.whl` file, which you can install using
   `pip`. Navigate to your project and install this Python wheel using your project's Python environment.

   ```bash
   AGENT_CATALOG_WHEEL_FILE=$(ls $(pwd)/dist/agentc-*.whl | tr -d '\n')

   # Make sure you are using your project's Python environment!
   cd $MY_AGENT_PROJECT
   source $MY_PYTHON_ENVIRONMENT

   pip install "$AGENT_CATALOG_WHEEL_FILE"
   ```

   To install the LangChain module associated with Agent Catalog, add `"[langchain]"` immediately after the wheel file:

   ```bash
   pip install "$AGENT_CATALOG_WHEEL_FILE""[langchain]"
   ```

5. You should now have the `agentc` command line tool. Run `agentc --help` to verify your installation (note that your
   first run will take a couple of seconds, subsequent runs will be faster).

   ```bash
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

     A command line tool for AGENT_CATALOG.

   Options:
     -c, --catalog DIRECTORY   Directory of local catalog files. The local catalog DIRECTORY should be checked into
                               git.  [default: .agent-catalog]
     -a, --activity DIRECTORY  Directory of local activity files (runtime data). The local activity DIRECTORY should
                               NOT be checked into git, as it holds runtime activity data like logs, etc.  [default:
                               .agent-activity]
     -v, --verbose             Enable verbose output.
     --help                    Show this message and exit.

   Commands:
     clean    Clean up the catalog folder, the activity folder, any generated files, etc.
     env      Show agentc's environment or configuration parameters as a JSON object.
     execute  Execute specific tool to test it.
     find     Find items from the catalog based on a natural language QUERY string.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     publish  Publish the local catalog to Couchbase DB.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com for more information.
   ```

   If you see the output above, you are all set! Head on over to our [docs](docs) or our [recipes](recipes) to start
   developing your agent with Agent Catalog.

## Building From Source

For examples on what an agentic workflow with `agentc` looks like, see
the [agent-catalog-example](https://github.com/couchbaselabs/agent-catalog-example) repository.

## Docs and Templates

Refer to [`docs/`](docs) to explore templates and other references while writing your agent workflow with Couchbase
Agent Catalog. We also provide some starter [`recipes`](recipes) if you are building an agent from scratch.

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

