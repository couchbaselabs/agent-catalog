# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.
_This README is intended for all `agent-catalog` contributors._

## Table of Contents

- [On Packages (inside `libs`)](#on-packages-inside-libs)
- [How to Contribute](#how-to-contribute)
- [Working with Poetry](#working-with-poetry)
- [On Testing (Pytest)](#on-testing-pytest)
- [Publishing Packages](#publishing-packages)
- [Generating `requirements.txt`](#generating-requirementstxt)

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
   _If you have any nested Git repositories due to working with examples, be sure to remove these before commiting!
   (e.g., `rm -r examples/with_langgraph/.git`)._

   ```bash
   git add $MODIFIED_FILES
   git commit
   git push
   ```

6. You should now see your branch on Github.
   On the Github page for this repo ([here](https://github.com/couchbaselabs/agent-catalog)), create a pull request
   (Pull Requests -> New Pull Request -> Create Pull Request).

   Use an appropriate title and description for your PR, and click "Create Pull Request" (or "Create Draft Pull
   Request" if this PR is in-progress).
   When all checks have passed, add reviewers on the right hand side.
   You must get at least one other contributor to review your PR before you can merge.

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

## On Testing (Pytest)

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export AGENT_CATALOG_DEBUG=true
```

### Running Unit Tests

To run the entire suite of unit tests, use the following `pytest` command in the project root:

```bash
pytest --log-file .output --log-level DEBUG
```

This command will a) run all tests according to the whitelist in `pyproject.toml` (i.e., `testpaths`), b) record the
logger output to a `.output` file, and c) set the logging level to DEBUG.

To only run smoke tests, use the following `pytest` command (again, from the project root):

```bash
pytest -m smoke --log-file .output --log-level DEBUG
```

To run tests for a specific package, use the following `pytest` command (again, from the project root):

```bash
pytest libs/agentc_core --log-file .output --log-level DEBUG
```

Note that Click doesn't play too well with pytest's `log_cli=true` option, so we recommend logging to a file.
For more information about Pytest's command line tool, see
[here](https://docs.pytest.org/en/stable/reference/reference.html#command-line-flags).

## Publishing Packages

**Packages on PyPI cannot be removed, only new packages can be pushed!**
**Ensure that all unit tests have passed before proceeding!**

1. Create a new branch in your local repository.

   ```bash
   git checkout -b dev/MAJOR.MINOR.PATCH_release
   ```

   Replace `MAJOR.MINOR.PATCH` with an incremented version number based off the previous release.
   Agent Catalog follows [semantic versioning](https://semver.org/), so be sure to increment accordingly.
   As a summary, version numbers follow a `MAJOR.MINOR.PATCH` format.

2. For all packages that need to be published, increment their version number in their respective `pyproject.toml`
   files (i.e., their `version` field in the `tool.poetry` section).
   Again, use semantic versioning here.

3. Commit these changes to your local repository and add a lightweight tag to your repository's HEAD.

   ```bash
   git tag vMAJOR.MINOR.PATCH
   ```

   Again, replace `MAJOR.MINOR.PATCH` with the version you used in step 1.

4. Push your branch to Github _with the new tag_:

   ```bash
   git push origin vMAJOR.MINOR.PATCH
   ```

5. Create a PR for your changes and merge your PR to master (see [How to Contribute](#how-to-contribute)).

6. Finally, create a Github release (which will trigger a workflow to publish to PyPI).
   On the Github page for this repo ([here](https://github.com/couchbaselabs/agent-catalog)), click
   "Create a New Release" under the "Releases" section.

   Choose the tag you published in step 4, and use this tag as the release title (e.g., the tag v0.1.0 has a release
   title of v.0.1.0).
   In the "Describe This Release" text box, describe how this release is different from the previous release as a
   Markdown list.
   You can use the "Generate Release Notes" to help you, but do your best to summarize the changes.
   See [here](https://gist.github.com/andreasonny83/24c733ae50cadf00fcf83bc8beaa8e6a) for an example.
   You should include i) Upgrade Steps, ii) Breaking Changes, iii) New Features, iv) Bug Fixes, and v) Improvements.

   If this release is non-production-ready, check the "Set as a Pre-Release" box.
   When you are finished with your changes, hit "Publish Release".
   This should trigger a Github workflow to publish the repository with the given tag to PyPI (specifically, the
   script `scripts/publish.sh` will run).


## Generating `requirements.txt`

To generate the top-level `requirements.txt` file, use `poetry export` and remove all editable references (i.e., those
that start with `-e` and possess local filesystem paths):

```bash
poetry export \
  -f requirements.txt \
  --without-hashes \
  --with agent-catalog \
  --with dev \
  | grep -v '^-e file' \
  > requirements.txt
```

