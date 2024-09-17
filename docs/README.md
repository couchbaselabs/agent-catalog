# Rosetta User Guide

Rosetta targets three (non-mutually-exclusive) types of users:

- **Agent Builders**: those responsible for creating prompts and agents.
- **Tool Builders**: those responsible for creating tools.
- **Agent Analysts**: those responsible for analyzing agent performance.

In this guide, we detail the workflow each type of user follows when using Rosetta.
We assume that you have already installed the Rosetta package. If you have not, please refer to the main (top-level)
README file.

## Using Rosetta for Metrics-Driven Development

The Rosetta package is not just a tool/prompt catalog, it's a foundation for building agents using metrics-driven
development. Agent builders will follow this workflow:

1. **Sample Downloading**: Download the sample agent from the `rosetta-example` repository.
2. **Agent Building**: The sample agent is meant to be a reference for building your own agents. You will need to
   modify the agent to fit your use case.
    - Rosetta integrates with agent applications in two main areas: i) by providing tools and prompts to the agent
      _framework_ via `rosetta.Provider` instances, and ii) by providing auditing capabilities to the agent application
      via `rosetta.Auditor` instances. The sample agent demonstrates how to use both of these classes.
    - Rosetta catalog providers will always return plain ol' Python functions. SQL++ tools, semantic search tools, and
      HTTP request tools undergo some code _generation_ (in the traditional sense, not using LLMs) to yield Python
      functions that will easily slot into any agent framework.
    - Python tools indexed by Rosetta will be returned as-is. _Users must ensure that these tools already exist in the
      agent application's Git repository, or that the Python source code tied to the tool can be easily imported using
      Python's `import ___` statement._
3. **Prompt Building**: Follow the steps outlined in the "Publishing to the Catalog" section above to create prompts.
    - In a multi-team setting, you can also use `rosetta find --kind prompt` to see if other team members have already
      created prompts that address your use case.
    - To accelerate prompt building, you can specify your tool requirements in the prompt. This will allow Rosetta to
      automatically fetch the tools you need when the prompt is executed.
4. **Agent Execution**: Run your agent! Depending on how your `rosetta.Auditor` instances are configured, you should
   see logs in the `./rosetta-activity` directory and/or in the `rosetta_logs` scope of your Couchbase instance.


## Publishing to the Catalog

The Rosetta catalog (currently) versions two types of items: tools and prompts.
Both tool builders and prompt builders (i.e., agent builders) will follow this workflow:

1. **Template Downloading**: Download the appropriate template from the `templates` directory.
2. **Tool/Prompt Creation**: Fill out the template with the necessary information.
3. **Versioning**: All tools and all prompts must be versioned. Rosetta currently integrates with Git (using the
   working Git SHA) to version each item. **You must be in a Git repository to use Rosetta.**
4. **Indexing**: Use the command `rosetta index [DIRECTORY] --kind [tool|prompt]` to index your tools/prompts, where
   `[DIRECTORY]` refers to the directory containing your tools/prompts. This will create a local catalog and your items
   will be in the newly created `./rosetta-catalog` folder.
5. **Publishing**: By default, the `rosetta index` command will allow you index tools / prompts associated with a dirty
   Git repository.
    1. To publish your items to a Couchbase instance, you must first commit your changes (to Git) and run the
       `rosetta index` command on a clean Git repository.
    2. Next, you must add your Couchbase connection string, username, and password to the environment. The most
       straightforward way to do this is by running the following commands:
       ```bash
       export ROSETTA_CONN_STRING=couchbase://localhost
       export ROSETTA_USERNAME=Administrator
       export ROSETTA_PASSWORD=password
       ```
    3. Use the command `rosetta publish --kind [tool|prompt|all] --bucket [BUCKET_NAME]` to publish your items to your
       Couchbase instance. This will create a new scope in the specified bucket called `rosetta_catalog`, which will
       contain all of your items.
    4. Note that Rosetta isn't meant for the "publish once and forget" case. You are encouraged to run the
       `rosetta publish` command as often as you like to keep your items up-to-date.

## Using Rosetta for Agent Analysis

The Rosetta package also provides a foundation for analyzing agent performance. Agent analysts will follow this
workflow:

1. **Log Access**: Your first step is to get access to the `rosetta.Auditor` captured logs. For logs sent to Couchbase,
   you can find them in the `rosetta_logs` scope of your Couchbase instance. For logs stored locally, you can find them
   in the `./rosetta-activity` directory. _We recommend the former, as it allows for easy ad-hoc analysis through
   Couchbase Query and/or Couchbase Analytics._
2. **Log Analysis**: For users with Couchbase Analytics enabled, we provide three views to help you get started with
   conversational-based agents:
    1. `Sessions (sid, start_t, vid, msgs)`, which provides one record per session (alt. trajectory). Each session
       record contains the session ID `sid`, the start time `start_t`, the catalog version `vid`, and a list of messages
       `msgs`. The `msgs` field details all events that occurred during the session (e.g., the user's messages, the
       response to the user, the internal "thinking" performed by the agent, the agent's transitions between tasks,
       etc...).
    2. `Exchanges (sid, question, answer, walk)`, which provides one record per exchange (i.e., the period between a
       user question and an assistant response) in a given session. Each exchange record contains the session ID `sid`,
       the user's question `question`, the agent's answer `answer`, and the agent's walk `walk` (e.g., the messages sent
       to the LLMs, the tools executed, etc...).
   3. `ToolCalls (sid, vid, tool_calls)`, which provides one record per session (alt. trajectory). Each tool call
      record contains the session ID `sid`, the catalog version `vid`, and a list of tool calls `tool_calls`. The
      `tool_calls` field details all information around an LLM tool call (e.g., the tool name, the tool-call arguments,
      and the tool result).
3. **Log Visualization**: Users are free to define their own views from the steps above and visualize their results
   using dashboards like [Tableau](https://exchange.tableau.com/en-us/products/627) or
   [Grafana](https://developer.couchbase.com/grafana-dashboards).
