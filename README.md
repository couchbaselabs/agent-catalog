# agent-catalog

User facing repository for all things agent-catalog (tooling around agent workflows).

## Building From Source

1. Ensure that you have `python3.11` and `poetry` installed.
   ```bash
   python3 -m pip install poetry
   ```
2. Clone this repository -- make sure that you have an SSH key setup!
   ```bash
   git clone git@github.com:couchbaselabs/rosetta.git
   ```
3. Install the dependencies from `pyproject.toml`.
   ```bash
   poetry install
   ```
4. To install the LangChain extra package, add `-E langchain` after `install`.
   ```bash
   poetry install -E langchain
   ```

For examples on what an agentic workflow with Rosetta looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

## Docs and templates

Refer to [`docs/`](docs) to explore templates and other references while writing your agent workflow with agent_catalog.

## For Contributors / Developers

### On Child Repositories

At the moment, there exists two child repositories:

1. [`rosetta-core`](https://github.com/couchbaselabs/rosetta-core), which implements the core functionality of
   `agentc` in an "un-opinionated" manner, and...
2. [`rosetta-lc`](https://github.com/couchbaselabs/rosetta-example), which supplies additional tooling around building
   LangChain-specific agents.

This repository (`rosetta`) is meant to serve as a "front-desk", where we focus on _setting defaults_
(i.e., being opinionated) for the sake of a simpler / more-user-friendly out-of-the-box experience.
Keep this in mind when contributing to these repositories: the core should be minimal and extensible, and this
repository should leverage the core's extensibility.

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
export ROSETTA_DEBUG=1
```

