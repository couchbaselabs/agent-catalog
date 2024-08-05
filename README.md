# rosetta-core

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
4. You should now have the `rosetta` command line tool installed.
   Run the `rosetta` command to test your installation.
   ```bash
   rosetta
   ```
5. To build a `.whl` file for distribution, run the command below.
   Your `.whl` file will show up under the `dist` folder.
   ```bash
   poetry build
   ```

   .
   .
   .

Once you have the `.whl` file, use `pip` to install this `rosetta` build in another project to define agentic workflows!
```bash
pip install dist/rosetta_core-*.*.*-py3-*-any.whl
```
For examples on what an agentic workflow with Rosetta looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.


## For Contributors / Developers

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

rosetta/
cmd/
  main.py       -- Main entry point for rosetta command-line tool (CLI).
  cmds/         -- Each "rosetta SUBCMD" has its own cmds/SUBCMD.py file.
    ...
    find.py
    index.py
    publish.py
    version.py
    web.py      -- Provides an HTML/REST interface for the SUBCMD's.

core/           -- The core rosetta library used by applications
                   and by the rosetta CLI.

tests/ -- Test cases.

VERSION.txt -- To be generated or updated at build or packaging time.
```