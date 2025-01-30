# A Research Agent

This directory contains a starter project for building agents with Couchbase, Langgraph, and Agent Catalog.

## Getting Started

### Running Your Agent

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Clone this repository and navigate to this directory (we will assume all subsequent commands are run from here).

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   cd templates/agents/with_langgraph
   ```

3. Agent Catalog uses Git for its versioning.
   Run the command below to initialize a new Git repository within the `templates/agents/with_langgraph` directory.

   ```bash
   git init
   git add * ; git add .gitignore .env.example
   git commit -m "Initial commit"
   ```

4. Installing anaconda.
   We recommend using Anaconda to create a virtual environment for your project to ensure no global dependencies interfere with the project.

   [Click here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) for Anaconda installation steps.

5. Install this project with Poetry from Makefile.

   Ensure you have Anaconda and Make installed (`make` for [MacOS](https://formulae.brew.sh/formula/make), [Windows](https://gnuwin32.sourceforge.net/packages/make.htm), [Ubuntu](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/)).

   Run the following commands to create and activate a virtual environment using Anaconda and install all the requirements required to run this example.

   Replace `research_agent` with any other suitable environment name.
   ```bash
   make lg-poetry env_name=research_agent
   conda activate research_agent
   ```

   Alternatively, you can install the project with `pip` with the following commands.
   ```bash
   make lg-pip env_name=research_agent
   conda activate research_agent
   ```

6. Manually install this project.

   Create a virtual environment either using Anaconda or any other Python environment manager.
   ```bash
   # create venv using Anaconda
   conda create -n research_agent python=3.12
   conda activate research_agent
   ```

   Install the example using Poetry
   ```bash
   poetry install
   ```

   Alternatively, install the example using `pip`
   ```bash
   pip install ../../../libs/agentc
   pip install ../../../libs/agentc_langchain
   ```

7. Run `agentc` to make sure this project has installed correctly (note that your first run will take a couple of
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
     clean    Delete all or specific (catalog and/or activity) agent related files / collections.
     env      Return all agentc related environment and configuration parameters as a JSON object.
     execute  Search and execute a specific tool.
     find     Find items from the catalog based on a natural language QUERY string or by name.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     init     Initialize the necessary files/collections for local/database catalog.
     ls       List all indexed tools and/or prompts in the catalog.
     publish  Upload the local catalog and/or logs to a Couchbase instance.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com or https://couchbaselabs.github.io/agent-catalog/index.html# for more information.
   ```

9. Initialize the local catalog and auditor.

   ```bash
   agentc init local all
   ```

   This command will create the necessary directories for the local catalog and auditor.

9. Make sure your Git repo is clean, and run `agentc index` to index your tools and prompts.
   Note that `tools` and `prompts` are _relative paths_ to the `tools` and `prompts` folder.

   ```bash
   # agentc index $PATH_TO_TOOLS_FOLDER $PATH_TO_PROMPTS_FOLDER
   agentc index tools prompts
   ```

   The command will subsequently crawl the `tools` and `prompts` folder for both tools and prompts.

   _Hint: if you've made changes but want to keep the same commit ID for the later "publish" step, use
   `git add $MY_FILES` followed by `git commit --amend`!_

10. Start up a Couchbase instance.

    1. For those interested in using a local Couchbase instance, see
       [here](https://docs.couchbase.com/server/current/install/install-intro.html).
    2. For those interested in using Couchbase within a Docker container, run the command below:

       ```bash
       mkdir -p .data/couchbase
       docker run -d --name my_couchbase \
         -p 8091-8096:8091-8096 -p 11210-11211:11210-11211 \
         -v "$(pwd)/.data/couchbase:/opt/couchbase/var" \
         couchbase
       ```

    3. For those interested in using Capella, see [here](https://cloud.couchbase.com/sign-up).

    Once Couchbase instance is running, enable the following services on your Couchbase cluster:
     - Data, Query, Index: For storing items and searching them.
     - Search: For performing vector search on items.
     - Analytics: For creating views on audit logs and to query the views for better insights on logs.

   This specific agent also uses the `travel-sample` bucket.
   You'll need to navigate to your instance's UI (for local instances, this is on http://localhost:8091) to import
   this sample bucket.

11. Create a `.env` file using `.env.example` as a reference and tweak it according to your environment.

   ```bash
   cp .env.example .env
   vi .env
   ```

12. Initialize the database catalog and auditor.

   ```bash
   agentc init db all --bucket travel-sample
   ```

    This command will create the necessary scopes, collections, secondary indexes, vector indexes and analytics views for the database catalog and auditor.

13. Publish your local agent catalog to your Couchbase instance with `agentc publish`.
   Your Couchbase instance details in the `.env` file will be used for authentication.
   Again, this specific starter agent uses the `travel-sample` bucket.

   ```bash
   agentc publish tool prompt --bucket travel-sample
   ```

14. Run your agent!

   To start jupyter server, run the following command:

    ```bash
    poetry run jupyter notebook
    ```

   Once the server is running, open the `agent.ipynb` notebook and execute it to interact with your agent.