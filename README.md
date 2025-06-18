# agent-catalog (Couchbase Agent Catalog)

[![CI/CD Tests](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml/badge.svg)](https://github.com/couchbaselabs/agent-catalog/actions/workflows/tests.yaml)

The mono-repo for the Couchbase Agent Catalog project.

## Table of Contents

- [Getting Started](#getting-started)
    * [Installing from Package](#installing-from-package)
    * [Installing from Source (with Makefile)](#installing-from-source-with-makefile)
    * [Installing from Source (with Poetry)](#installing-from-source-with-poetry)
- [Docs and Templates](#docs-and-templates)

## Getting Started

### Installing from Package

(in the works!)

### Installing from Source (with Makefile)

1. Make sure you have `python3.12` and [`poetry`](https://python-poetry.org/docs/#installation) installed!

2. Make sure you have `make` installed!
   For Mac-based installations, see [here](https://formulae.brew.sh/formula/make).
   For Windows-based installations, see [here](https://gnuwin32.sourceforge.net/packages/make.htm).
   For Ubuntu-based installations, see [here](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/).

3. Clone this repository.

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   ```

4. Navigate to the `agent-catalog` directory and run `make`.
   This will a) create a new virtual environment using Poetry and b) install all required packages and CLI tools.

5. Activate your newly created virtual environment using the outputs of `make activate` or `poetry env activate`.
   If you do not want to copy-and-paste the output, you can run the command with `eval`:

   ```bash
   eval $(poetry env activate)
   ```

   If your environment has been successfully activated, you should see `(Activated)` after running `poetry env list`...
   ```bash
   poetry env list
   > agent-catalog-UEfqTvAT-py3.13 (Activated)
   ```

   ...**and** you should see that your `python` now points to the python in your virtual environment (not your system
   default).
   ```bash
   which python
   > /Users/....../Library/Caches/pypoetry/virtualenvs/agent-catalog-UEfqTvAT-py3.13/bin/python
   ```

6. If you are interested in building a `.whl` file (for later use in `.whl`-based installation in other projects),
   run the following command:

   ```bash
   cd libs/agentc
   poetry build
   ```

### Installing from Source (with Anaconda)

1. Make sure you have `python3.12` and
   [`conda`](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) installed!

2. Create a new virtual environment with Anaconda and subsequently activate your environment.
   Again, you must activate your environment before running any `agentc` commands!
   ```bash
   conda create -n my_agentc_env python=3.12
   conda activate my_agentc_env
   ```

3. Navigate to this directory and install Agent Catalog with `pip`:
   ```bash
   cd agent-catalog

   # Install the agentc package.
   pip install libs/agentc
   ```

   If you are interested in developing with LangChain or LangGraph, install the helper `agentc_langchain` and/or
   `agentc_langgraph` packages with the command below:
   ```bash
   pip install libs/agentc_integrations/langchain
   pip install libs/agentc_integrations/langgraph
   ```

   ...and for those working with LlamaIndex:
   ```bash
   pip install libs/agentc_integrations/llamaindex
   ```

## Docs and Templates

Refer to [`docs/`](docs) to build our technical documentation (also hosted
[here](https://couchbaselabs.github.io/agent-catalog/index.html)) and explore Couchbase Agent Catalog before authoring
your agent applications.

## Disclaimer
The agent_catalog library is still in development and is not ready for production use. Use it at your own risk.

This library is a non-GA offering.  Non-GA Offerings are provided without support or any servicing obligations, and may contain bugs and other functional issues. NON-GA OFFERINGS ARE PROVIDED AS-IS AND WITHOUT ANY WARRANTY OR INDEMNITY. Couchbase, its affiliates, and its licensors are not liable for any harm or damages related to Non-GA Offerings. Couchbase may discontinue Non-GA Offerings at any time in its sole discretion and is under no obligation to make Non-GA Offerings generally available. By utilizing the agent_catalog library, you acknowledge and accept these parameters.