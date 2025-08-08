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
%%{init: {'flowchart': {'curve': 'linear', 'defaultRenderer': 'elk'}}}%%
graph BT
;
    __start__([<p>__start__</p>]):::first
    front_desk_agent(front_desk_agent)
    endpoint_finding_agent(endpoint_finding_agent)
    route_finding_agent(route_finding_agent)
    __end__([<p>__end__</p>]):::last
    __start__ --> front_desk_agent;
    endpoint_finding_agent --> route_finding_agent;
    front_desk_agent -. ENDPOINT_FINDING .-> endpoint_finding_agent;
front_desk_agent -. END .-> __end__;
route_finding_agent -. FRONT_DESK .-> front_desk_agent;
route_finding_agent -. ENDPOINT_FINDING .-> endpoint_finding_agent;
front_desk_agent -. FRONT_DESK .-> front_desk_agent;
classDef default fill:#f2f0ff, line-height: 1.2
classDef first fill-opacity:0
classDef last fill: #bfb6fc
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
   > /Users/$USER/Library/Caches/pypoetry/virtualenvs/with-langgraph-example-gJ1RHvkw-py3.12/bin/python
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
   In this example, we will also add a post-commit hook to integrate `agentc` with your existing `git` workflow.

   ```bash
   agentc init --add-hook-for tools --add-hook-for prompts
   ```

4. Now let us make our first commit, which will use `agentc` behind the scenes.

   ```bash
   git add * ; git add .gitignore .env.example .pre-commit-config.yaml
   git commit -m "Initial commit"
   ```

   _Hint: if you've made changes but want to keep the "same" commit within your local branch, use
   `git add $MY_FILES` followed by `git commit --amend`!_

5. Finally, run your agent system and talk with the "Front Desk" agent!

   ```bash
   python main.py
   ```

### (Ad-Hoc) Tuning Your Agent System

In this section, we will illustrate how you can "tune" your agent system in an ad-hoc (but provenance-capturing) manner.

1. To start, let's find a route from SFO to LAX.

    ```text
   > Assistant: Please provide the source and destination airports.
   > User: I want to go to LA. I am from the bay area
   > Assistant: I found several direct flight options from the Bay Area to Los Angeles (LAX). Here are the details:

   ### From San Francisco International Airport (SFO):
   - Airlines: Alaska Airlines (AS), Delta Airlines (DL), United Airlines (UA), US Airways (US), Virgin America (VX),
     Southwest Airlines (WN), American Airlines (AA)

   ### From Oakland International Airport (OAK):
   - Airlines: Delta Airlines (DL), Frontier Airlines (FL), Southwest Airlines (WN)

   ### From San Jose International Airport (SJC):
   - Airlines: Alaska Airlines (AS), Delta Airlines (DL), Frontier Airlines (FL), Singapore Airlines (SQ),
     United Airlines (UA), US Airways (US), Virgin America (VX), Southwest Airlines (WN), American Airlines (AA)

   You can choose any of these airports based on your convenience. Would you like more information on any specific
   flight or airline?
    ```

   We can view the path on our graph we traversed by querying our logs collection (below is an Analytics query):

   ```sql
   SELECT
    *
   FROM
    `travel-sample`.agent_activity.Sessions t
   WHERE
    t.sid = `travel-sample`.agent_activity.LastSession()
   ```

2. Next, let's try a set of endpoints that has requires one layover.
   Specifically, we want a route from Canyonlands Field Airport (IATA 'CNY') to LAX.
   We will restart our agent and converse with our agent accordingly:

   ```text
   > Assistant: Please provide the source and destination airports.
   > User: i want to go to LAX from Canyonlands Field Airport
   > Assistant: To travel from Canyonlands Field Airport (CNY) to Los Angeles International Airport (LAX), you have a
   few options:

   1. **Direct Flight**: Check for any direct flights from Canyonlands Field Airport to LAX. However, direct flights
      may not be available, and you might need to connect through another airport.

   2. **Connecting Flights**: If there are no direct flights, you can look for connecting flights. Common connecting
   airports include Salt Lake City International Airport (SLC) or Denver International Airport (DEN). You would fly
   from CNY to one of these airports and then catch a flight to LAX.

   3. **Driving**: If you prefer to drive, the distance from Canyonlands Field Airport to LAX is approximately 700
   miles. The drive would take around 10-12 hours, depending on traffic and road conditions. You would take US-191 S
   to I-70 W, then connect to I-15 S towards Los Angeles.

   4. **Bus or Shuttle Services**: Check if there are any bus or shuttle services that operate between these two
   locations, although this option may take significantly longer.

   Make sure to check flight availability and book in advance if you choose to fly. Safe travels!
   ```

   This is **not** a correct response.
   If we take a look at our logs (again, issuing the SQL query on ``Sessions`` above), we see that the culprit lies
   with our "Front Desk" agent incorrectly assuming the user input is not relevant to route planning.

   1. To fix this, let us modify our prompt.
      Open the file `prompts/front_desk.yaml` and uncomment all items in the  `content --> agent_instructions` list.

   2. Next, we will create a new commit that captures this change.

      ```bash
      git add prompts/front_desk.yaml ; git commit -m "Fixing front desk agent."
      ```

   3. Now, let us try the same input again with our agent system.

       ```text
       > Assistant: Please provide the source and destination airports.
       > User: i want to go to LAX from Canyonlands Field Airport
       > Assistant: There are no direct flights from Canyonlands Field Airport (CNY) to Los Angeles International
      Airport (LAX). However, there are several one-layover flights available with a stop in Salt Lake City (SLC).
      Here are the options:

       1. **Delta Airlines (DL) to Alaska Airlines (AS)** with a layover in SLC.
       2. **Delta Airlines (DL) to Delta Airlines (DL)** with a layover in SLC.
       3. **Delta Airlines (DL) to KLM (KL)** with a layover in SLC.
       4. **Delta Airlines (DL) to United Airlines (UA)** with a layover in SLC.
       5. **Delta Airlines (DL) to US Airways (US)** with a layover in SLC.
       6. **Delta Airlines (DL) to Southwest Airlines (WN)** with a layover in SLC.
       7. **Delta Airlines (DL) to American Airlines (AA)** with a layover in SLC.

       You can choose any of these options based on your preference for airlines and schedule.
       > User: that's all, thanks
       > Assistant: You're welcome! If you have any more questions in the future, feel free to reach out. Safe travels!
       ```

      ...and it seems our fix has worked!

### Evaluating Your Agent System

In this section, we will now illustrate some building blocks for authoring your own set of evaluations.
_We assume that the previous section has not been run (i.e., the "i want to go to LAX from Canyonlands Field Airport"
input is not working)._

1. Enter the command below to execute two prebuilt evaluation suites (`eval_bad_intro` and `eval_short_threads`)
   three separate times.

   ```bash
   for i in {1..3}; do pytest evals -v; done
   ```

   *Get some coffee, this will take some time!*
   Once this command is run, you should see logs generated by these evaluations in your `.agent-activity` folder and
   `agent_activity.logs` collection with `span.name` values starting with either `"IrrelevantGreetings"` or
   `"ShortThreads"` followed by `"Eval_[0-9]"`  **but** with the same subsequent name parts used in the rest of our
   application (e.g., `"flight_planner"`, `"front_desk_node"`).

2. Next, let's take a closer look at the file `evals/eval_short.py`.
   This sample application has two "eval" functions: one to make sure that our agent application does not respond to
   irrelevant greetings and another to make sure that our agent application responds "correctly" to short 1-2 turn
   conversations.

   1. To evaluate irrelevant greetings, we stop at the first response given by our application.
      If our application has not correctly determined that the conversation needs to end, then we use the `[]` operator
      on our span to record this (as `correctly_set_is_last_step`).
   2. To evaluate whether (or not) our application has correctly answered a user's request, we use Ragas's
      "simple criteria score" to use an LLM (in our case, `gpt-4o`, to return a number between 0 and 5 based on the
      similarity of answers (i.e., "references").

3. Now let's take a closer look at these logs on Couchbase.
   Log onto your Couchbase instance and let's write two queries for the evaluations we just ran (in this example,
   we'll use the Analytics Service):
   *We assume some familiarity with SQL++ here.*

   1. First, does our agent reliably feign off bad introductions?
      Specifically, what is the percentage of instances that our agent properly handles an irrelevant introduction?

      ```sql
         WITH
            irrelevant_greetings AS (
                FROM
                    `travel-sample`.agent_activity.logs AS l
                WHERE
                     l.content.kind = "key-value" AND
                     l.content.`key` = "correctly_set_is_last_step" AND
                     "IrrelevantGreetings" IN l.span.name
                SELECT VALUE l.content.`value`
            ),
            correct_runs AS ( FROM irrelevant_greetings AS ig WHERE ig SELECT VALUE COUNT(*) )[0],
            incorrect_runs AS ( FROM irrelevant_greetings AS ig WHERE NOT ig SELECT VALUE COUNT(*) )[0]
         SELECT VALUE
            correct_runs / incorrect_runs;
      ```

      For my runs I see a 50% success rate, suggesting that our front desk agent needs to be modified to properly
      recognize irrelevant greetings (some ideas here include reducing the surface area of user input through more
      restrictive UI or more intelligent intent recognition).

   2. Next, what is the average "goal accuracy" of our latest application version?

      ```sql
         WITH latest_catalog_version AS (
            FROM
                `travel-sample`.agent_catalog.metadata AS m
            SELECT VALUE
                m.version.identifier
            ORDER BY
                STR_TO_MILLIS(m.version.timestamp) DESC
         )[0]
         FROM
            `travel-sample`.agent_activity.logs AS l
         WHERE
            l.content.kind = "key-value" AND
            l.content.`key` = "goal_accuracy" AND
            l.catalog_version.identifier = latest_catalog_version
         SELECT VALUE
            AVG(l.content.`value`.score);
      ```

      For my runs I get an average score of 1.44 with one of the "problematic" inputs being the
      "Canyonlands Field Airport CNY" input.
