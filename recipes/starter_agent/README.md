# A Starter Agent

This directory contains a starter project for building agents with Couchbase, ControlFlow, and Agent Catalog.

## Getting Started

1. Make sure you have Python 3.12 and [Poetry](https://python-poetry.org/docs/#installation) installed!
2. Install this project with Poetry.

   ```bash
   poetry install
   ```

3. Run `agentc` to make sure this project has installed correctly (note that your first run will take a couple of
   seconds, subsequent runs will be faster).

   ```bash
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

     A command line tool for AGENT_CATALOG.

   Options:
     -c, --catalog DIRECTORY   Directory of local catalog files. The local catalog DIRECTORY should be checked into
                               git.  [default: .agent-catalog]
     -a, --activity DIRECTORY  Directory of local activity files (runtime data). The local activity DIRECTORY should
                               NOT be checked into git, as it holds runtime activity data like logs, etc.  [default:
                               .agent-activity]
     -v, --verbose             Enable verbose output.
     --help                    Show this message and exit.

   Commands:
     clean    Clean up the catalog folder, the activity folder, any generated files, etc.
     env      Show agentc's environment or configuration parameters as a JSON object.
     execute  Execute specific tool to test it.
     find     Find items from the catalog based on a natural language QUERY string.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     publish  Publish the local catalog to Couchbase DB.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com for more information.
   ```

4. Make sure your Git repo is clean, and run `agentc index` to index your tools and prompts.

   ```bash
   agentc index --kind tool tools
   agentc index --kind prompt prompts
   ```

5. Start up a Couchbase instance (see[here](https://docs.couchbase.com/server/current/install/install-intro.html) for
   instructions on how to run Couchbase locally).
6. Create a `.env` file from the `.env.example` file and tweak this to your environment.

   ```bash
   cp .env.example .env
   vi .env
   ```

7. Publish your local agent catalog to your Couchbase instance with `agentc publish`. Your Couchbase instance details
   in the `.env` file will be used for authentication. This starter agent uses the `travel-sample` bucket.

   ```bash
   agentc publish --kind all --bucket travel-sample
   ```

8. Start a prefect server and run your agent!

   ```bash
   prefect server start &
   python agent.py
   ```