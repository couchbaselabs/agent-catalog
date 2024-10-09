# agent-catalog-core

The core for a Couchbase-backed agentic workflow SDK.

## Building From Source

1. Ensure that you have `python3.11` and `poetry` installed.
   ```bash
   python3 -m pip install poetry
   ```
2. Clone this repository -- make sure that you have an SSH key setup!
   ```bash
   git clone git@github.com:couchbaselabs/rosetta-core.git
   ```
3. Install the dependencies from `pyproject.toml`.
   ```bash
   poetry install
   ```
4. You should now have the `agentc` command line tool installed.
   Run the `agentc` command to test your installation.
   ```bash
   agentc
   ```
   ```
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

   A command line tool for Rosetta.

   Options:
     -c, --catalog DIRECTORY   Directory of local catalog files. The local
                               catalog DIRECTORY should be checked into git.
                               [default: .agent-catalog]
     -a, --activity DIRECTORY  Directory of local activity files (runtime data).
                               The local activity DIRECTORY should NOT be checked
                               into git, as it holds runtime activity data like
                               logs, call histories, etc.  [default: .agent-
                               activity]
     -v, --verbose             Enable verbose output.
     --help                    Show this message and exit.

   Commands:
     clean    Clean up catalog, activity, generated files, etc.
     env      Show this program's env or configuration parameters as JSON.
     find     Find tools, prompts, etc.
     index    Walk source directory trees for indexing source files into the...
     publish  Publish the local catalog to a database.
     status   Show the status of the local catalog.
     version  Show the version of this tool.
     web      Start local web server.
   ```

For examples on what an agentic workflow with Rosetta looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

## For Contributors / Developers

### Setting up Pre-Commit

To set up `pre-commit` and reap all the benefits of code formatting, linting, automatic `poetry` lock generation, etc...
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

### Working with Poetry

Below, we list out some notes that developers might find useful w.r.t. Poetry:

1. Before committing, always use `poetry update; poetry lock`!
   This will check if the dependencies laid out in the `pyproject.toml` file are satisfiable and will repopulate the
   lock file appropriately.
2. `poetry install` vs. `poetry update`: in the presence of a `poetry.lock` file (which we do have), the former will
   only consider installing packages specified in the lock file.
   The latter (`poetry update`) will read from the `pyproject.toml` file and try to resolve dependencies from there.

### Project Structure

Below, we lay out some important directories & files.

```
README.md
pyproject.toml

cmd/
   main.py       -- Main entry point for agent command-line tool (CLI).
   defaults.py   -- All command-line-tool defaults belong in here.
   cmds/         -- Each "agentc SUBCMD" has its own cmds/SUBCMD.py file.
      ...
      find.py
      index.py
      publish.py
      version.py
      web.py      -- Provides an HTML/REST interface for the SUBCMD's.
   models/

core/     -- The core agentc library used by applications and by the agentc CLI.
   catalog/
   provider/
   record/
   secrets/
   tool/
   version/

tests/            -- Test cases.

VERSION.txt       -- To be generated or updated at build or packaging time.
```