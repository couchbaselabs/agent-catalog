# A Starter Researcher Application

This directory contains a starter project for building agents with Couchbase, LangGraph, and Agent Catalog in a tidy
Jupyter notebook.

## Getting Started

### Installing Agent Catalog

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Clone this repository and navigate to this directory (we will assume all subsequent commands are run from here).

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   cd examples/with_notebook
   ```

3. Install this example using Poetry.
   By default, Poetry will create a new virtual environment to hold this project.
   ```bash
   poetry install
   ```

4. Activate your newly created virtual environment.
   **You must be in this virtual environment for all subsequent commands to properly execute!**

   ```bash
   poetry shell
   ```

   In your shell, you should now see something similar below if you run `which python`:
   ```bash
   which python
   > /Users/$USER/Library/Caches/pypoetry/virtualenvs/with-notebook-example-gJ1RHvkw-py3.12/bin/python
   ```

5. Run `agentc` to make sure this project has installed correctly (note that your first run will take a couple of
   seconds as certain packages need to be compiled, subsequent runs will be faster).

### Setting Up Couchbase + Agent Catalog


1. Create a `.env` file from the `.env.example` file and tweak this to your environment.

   ```bash
   cp .env.example .env
   vi .env
   ```

   If you are using Capella, you'll need to download a security certificate and set the
   `AGENT_CATALOG_CONN_ROOT_CERTIFICATE` and `CB_CERTIFICATE` variables appropriately.

2. Start up a Couchbase instance.

   - For those interested in using a local Couchbase instance, see
     [here](https://docs.couchbase.com/server/current/install/install-intro.html).

   - For those interested in using Couchbase within a Docker container, run the command below:

       ```bash
       mkdir -p .data/couchbase
       docker run -d --name my_couchbase \
         -p 8091-8096:8091-8096 -p 11210-11211:11210-11211 \
         -v "$(pwd)/.data/couchbase:/opt/couchbase/var" \
         couchbase
       ```

   - For those interested in using Capella, see [here](https://cloud.couchbase.com/sign-up).

   Once your Couchbase instance is running, be sure to enable the following services on your Couchbase cluster:
   i) Data, ii) Query, iii) Index, iv) Search, and v) Analytics.

   This specific agent also uses the `travel-sample` bucket.
   You'll need to navigate to your instance's UI (for local instances, this is on http://localhost:8091) to install
   this sample bucket.

3. Initialize your local and Couchbase-hosted Agent Catalog instance by running the `agentc init` command.

   ```bash
   agentc init
   ```

4. Agent Catalog uses Git for its versioning, and acts seamlessly as a Git post-commit hook.

   Run the command below to initialize a new Git repository within the `examples/with_notebook` directory and install
   the Agent Catalog hooks.

   ```bash
   git init
   pre-commit install --hook-type post-commit --hook-type pre-commit
   ```

5. We will now make our first commit.
   Run the following to both commit and use Agent Catalog to index + publish your tools and prompts.

   ```bash
      git add * ; git add .gitignore .env.example .pre-commit-config.yaml
      git commit -m "Initial commit"
   ```

   If you have installed the post-commit hooks correctly (and the commit succeeds), you should see the following:

   ```text
   check for added large files..............................................Passed
   check toml...............................................................Passed
   check yaml...............................................................Passed
   check json...............................................................Passed
   check xml............................................(no files to check)Skipped
   fix end of files.........................................................Passed
   trim trailing whitespace.................................................Passed
   mixed line ending........................................................Passed
   ruff.....................................................................Passed
   format code with ruff....................................................Passed
   check toml...........................................(no files to check)Skipped
   check yaml...........................................(no files to check)Skipped
   check json...........................................(no files to check)Skipped
   check xml............................................(no files to check)Skipped
   mixed line ending....................................(no files to check)Skipped
   ruff.................................................(no files to check)Skipped
   format code with ruff................................(no files to check)Skipped
   index tools and prompts..................................................Passed
   publish tools and prompts................................................Passed
   [main (root-commit) e97fd87] Initial commit
    9 files changed, 633 insertions(+)
    create mode 100644 .env.example
    create mode 100644 .gitignore
    create mode 100644 .pre-commit-config.yaml
    create mode 100644 README.md
    create mode 100644 charter.yaml
    create mode 100644 pyproject.toml
    create mode 100644 researcher.ipynb
    create mode 100644 researcher.yaml
    create mode 100644 tools.py
   ```

### Running Your Agent System

1. First, start a Jupyter server by running the following command (remember, you must have your virtual environment
   activated!):

   ```bash
   jupyter notebook
   ```

2. Open and execute the `researcher.ipynb` notebook to interact with your agent!

