# A Starter Agent

This directory contains a starter project for building agents with Couchbase, ControlFlow, and Agent Catalog.

## Getting Started

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Navigate to this directory (we will assume all subsequent commands are run from here).

   ```bash
   cd templates/agents/with_controlflow
   ```

3. Install this project with Poetry (with the `analysis` group dependencies).

   ```bash
   poetry install --with analysis
   poetry shell
   ```

4. Run `agentc` to make sure this project has installed correctly (note that your first run will take a couple of
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

     See: https://docs.couchbase.com for more information.
   ```

5. Make sure your Git repo is clean, and run `agentc index` to index your tools and prompts.
   Note that `tools` and `prompts` are _relative paths_ to the `tools` and `prompts` folder.

   ```bash
   # agentc index $PATH_TO_TOOLS_FOLDER $PATH_TO_PROMPTS_FOLDER
   agentc index tools prompts
   ```

   The command will subsequently crawl the `tools` and `prompts` folder for both tools and prompts.

6. Start up a Couchbase instance.

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

   This specific agent also uses the `travel-sample` bucket.
   Be sure to log into your cluster and install this sample bucket.

7. Create a `.env` file from the `.env.example` file and tweak this to your environment.

   ```bash
   cp .env.example .env
   vi .env
   ```

8. Publish your local agent catalog to your Couchbase instance with `agentc publish`.
   Your Couchbase instance details in the `.env` file will be used for authentication.
   Again, this specific starter agent uses the `travel-sample` bucket.

   ```bash
   agentc publish tool prompt --bucket travel-sample
   ```

9. Start a prefect server and run your agent!

   ```bash
   export PREFECT_API_URL=http://127.0.0.1:4200/api
   prefect server start &
   python agent.py
   ```