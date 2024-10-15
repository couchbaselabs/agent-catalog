# agent-catalog

The mono-repo for the Couchbase Agent Catalog project.

## Building From Source

1. Ensure that you have `python3.12` and `poetry` installed.
   ```bash
   python3 -m pip install poetry
   ```
2. Clone this repository -- make sure that you have an SSH key setup!
   ```bash
   git clone git@github.com:couchbaselabs/agent-catalog.git
   ```
3. Create a virtual environment to manage dependencies
   ```bash
   conda create -n <venv_name> python=3.12
   conda activate <venv_name>
   # conda deactivate <venv_name> # to deactivate the virtual env after use
   ```
4. Install the dependencies from `pyproject.toml`.
   ```bash
   poetry install
   ```
5. To install the LangChain extra package, add `-E langchain` after `install`.
   ```bash
   poetry install -E langchain
   ```

For examples on what an agentic workflow with Agent Catalog looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

## Docs and templates

Refer to [`docs/`](docs) to explore templates and other references while writing your agent workflow with agent_catalog.

## For Contributors / Developers

### On Sub folders

All sdk code is wrapped under [`libs`](libs). Following are sub-folders that you can explore:

1. [`agent_catalog`](libs/agentc), which contains the classes to use with your agent development frameworks,
2. [`agent_catalog_libs`](libs/agentc_core), which implements the core functionality of
   `agentc` in an "un-opinionated" manner,
3. [`lc`](libs/agentc_langchain), which supplies additional tooling around building
   LangChain-specific agents.

This repository (`agent-catalog`) is meant to serve as a "front-desk", where we focus on _setting defaults_
(i.e., being opinionated) for the sake of a simpler / more-user-friendly out-of-the-box experience.
Keep this in mind when contributing to these repositories: libs should be minimal and extensible, and this
repository should leverage the libs' extensibility.

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

