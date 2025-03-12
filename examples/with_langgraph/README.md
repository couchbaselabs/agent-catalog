# A Starter Multi-Agent System

This directory contains a starter project for building agents with Couchbase, LangGraph, and Agent Catalog.

## A 3-Agent System

_We assume some familiarity with the
[Travel Sample Data Model](https://docs.couchbase.com/python-sdk/current/ref/travel-app-data-model.html) and the core
concepts of [LangGraph](https://langchain-ai.github.io/langgraph/)._

This starter project is meant to get new users familiar with the processes of building agents in a _principled_ manner.
In this project, there are three agents:

1. "Front Desk" -- Purposed to interact with the user and the "Endpoint Finding" agent.
2. "Endpoint Finding" -- Purposed to translate the user's input into IATA airport codes and interact with the
   "Route Finding" agent.
3. "Route Finding" -- Purposed to find routes using Couchbase tools between the endpoints provided by the
   "Endpoint Finding" and to i) interact with the "Endpoint Finding" agent to provide new endpoints if no routes are
   found or ii) send the routes (or lack of routes) to the "Front Desk" agent to give back to the user.

```mermaid
%%{init: {'flowchart': {'curve': 'linear'}}}%%
graph TD;
	__start__([<p>__start__</p>]):::first
	front_desk_agent(front_desk_agent)
	endpoint_finding_agent(endpoint_finding_agent)
	route_finding_agent(route_finding_agent)
	__end__([<p>__end__</p>]):::last
	__start__ --> front_desk_agent;
	endpoint_finding_agent --> route_finding_agent;
	front_desk_agent -. &nbsp;ENDPOINT_FINDING&nbsp; .-> endpoint_finding_agent;
	front_desk_agent -. &nbsp;END&nbsp; .-> __end__;
	route_finding_agent -. &nbsp;FRONT_DESK&nbsp; .-> front_desk_agent;
	route_finding_agent -. &nbsp;ENDPOINT_FINDING&nbsp; .-> endpoint_finding_agent;
	front_desk_agent -. &nbsp;FRONT_DESK&nbsp; .-> front_desk_agent;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

## Getting Started

### Installing Agent Catalog

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Clone this repository and navigate to this directory (we will assume all subsequent commands are run from here).

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   cd examples/with_langgraph
   ```

3. Agent Catalog uses Git for its versioning.

   Run the command below to initialize a new Git repository within the `examples/with_langgraph` directory.

   ```bash
   git init
   git add * ; git add .gitignore .env.example .pre-commit-config.yaml
   git commit -m "Initial commit"
   ```

4. Install this example using Poetry.
   By default, Poetry will create a new virtual environment to hold this project.
   ```bash
   poetry install --with analysis
   ```

5. Activate your newly created virtual environment.
   **You must be in this virtual environment for all subsequent commands to properly execute!**

   ```bash
   poetry shell
   ```

   In your shell, you should now see something similar below if you run `which python`:
   ```bash
   which python
   > /Users/$USER/Library/Caches/pypoetry/virtualenvs/my-agent-gJ1RHvkw-py3.12/bin/python
   ```

6. Run `agentc` to make sure this project has installed correctly (note that your first run will take a couple of
   seconds as certain packages need to be compiled, subsequent runs will be faster).

   ```bash
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

     The Couchbase Agent Catalog command line tool.

   Options:
     -c, --catalog DIRECTORY         Directory of the local catalog files.  [default: .agent-catalog]
     -a, --activity DIRECTORY        Directory of the local activity files (runtime data).  [default: .agent-activity]
     -v, --verbose                   Flag to enable verbose output.  [default: 0; 0<=x<=2]
     -i, --interactive / -ni, --no-interactive
                                     Flag to enable interactive mode.  [default: i]
     --help                          Show this message and exit.

   Commands:
     add      Interactively create a new tool or prompt and save it to the filesystem (output).
     clean    Delete all agent catalog related files / collections.
     env      Return all agentc related environment and configuration parameters as a JSON object.
     execute  Search and execute a specific tool.
     find     Find items from the catalog based on a natural language QUERY string or by name.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     publish  Upload the local catalog to a Couchbase instance.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com or https://couchbaselabs.github.io/agent-catalog/index.html# for more information.
   ```

### Running Your Agent System

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

4. Make sure your Git repo is clean, and run `agentc index` to index your tools and prompts.
   Note that `tools` and `prompts` are _relative paths_ to the `tools` and `prompts` folder.

   ```bash
   # agentc index $PATH_TO_TOOLS_FOLDER $PATH_TO_PROMPTS_FOLDER
   agentc index tools prompts
   ```

   This command will subsequently crawl the `tools` and `prompts` folder for both tool and prompt files.

   _Hint: if you've made changes but want to keep the same commit ID for the later "publish" step, use
   `git add $MY_FILES` followed by `git commit --amend`!_

5. Publish your local agent catalog to your Couchbase instance with `agentc publish`.
   Your Couchbase instance details in the `.env` file will be used for authentication.
   Again, this specific starter agent system uses the `travel-sample` bucket.

   ```bash
   agentc publish
   ```

    _Hint: feel free to install `agentc` as a post-commit hook!
    Run `pre-commit install --hook-type post-commit --hook-type pre-commit` to install this project's (pre|post)-commit
    hooks and run `agentc index` + `agentc publish` after `git commit [--amend]`!_

6. Run your agent system!

   ```bash
   python main.py
   ```

7. Let's now talk with the "Front Desk" agent!


### Evaluating Your Agent System

