# Agent Catalog Command Line Interface

Install the `agentc` package using the instructions in the [README.md](../../README.md).
   ```bash
   agentc
   # or agentc --help
   ```

   ```
   Usage: agentc [OPTIONS] COMMAND [ARGS]...

     A command line tool for AGENT_CATALOG.

   Options:
     -c, --catalog DIRECTORY   Directory of local catalog files. The local catalog DIRECTORY should be checked into git.  [default: .agent-catalog]
     -a, --activity DIRECTORY  Directory of local activity files (runtime data). The local activity DIRECTORY should NOT be checked into git, as it holds runtime activity data like logs, etc.  [default: .agent-activity]
     -v, --verbose             Enable verbose output.
     --help                    Show this message and exit.

   Commands:
     clean    Clean up the catalog folder, the activity folder, any generated files, etc.
     env      Show agentc's environment or configuration parameters as a JSON object.
     execute  Execute specific tool to test it with an agent.
     find     Find items from the catalog based on a natural language QUERY string.
     index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
     publish  Publish the local catalog to Couchbase DB.
     status   Show the status of the local catalog.
     version  Show the current version of agentc.

     See: https://docs.couchbase.com for more information.
   ```

