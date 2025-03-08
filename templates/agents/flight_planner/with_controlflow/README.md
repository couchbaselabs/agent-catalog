# A Starter Agent

This directory contains a starter project for building agents with Couchbase, ControlFlow, and Agent Catalog.

## Getting Started

### Running Your Agent

1. Make sure you have `python3.12` and [`poetry`](https://python-poetry.org/docs/#installation) installed!

2. Make sure you have `make` installed!
   For Mac-based installations, see [here](https://formulae.brew.sh/formula/make).
   For Windows-based installations, see [here](https://gnuwin32.sourceforge.net/packages/make.htm).
   For Ubuntu-based installations, see [here](https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/).

3. For ControlFlow (this specific agent framework), Rust needs to be installed.
   See [here](https://rustup.rs/) for installation instructions.

4. Clone this repository.

   ```bash
   git clone https://github.com/couchbaselabs/agent-catalog
   ```

5. Navigate to this directory `templates/agents/flight_planner/with_controlflow` directory and run `make`.
   This will a) create a new virtual environment using Poetry and b) install all required packages and CLI tools.

6. Agent Catalog uses Git for its versioning.
   Run the command below to initialize a new Git repository within the `templates/agents/with_controlflow` directory.

   ```bash
   git init
   git add * ; git add .gitignore .env.example
   git commit -m "Initial commit"
   ```

7. Activate your newly created virtual environment using the outputs of `make activate` or `poetry env activate`.
   If you do not want to copy-and-paste the output, you can run the command with `eval`:

   ```bash
   eval $(poetry env activate)
   ```

   If your environment has been successfully activated, you should see `(Activated)` after running `poetry env list`...
   ```bash
   poetry env list
   > my-agent-UEfqTvAT-py3.13 (Activated)
   ```

   ...**and** you should see that your `python` now points to the python in your virtual environment (not your system
   default).
   ```bash
   which python
   > /Users/....../Library/Caches/pypoetry/virtualenvs/my-agent-UEfqTvAT-py3.13/bin/python
   ```

   _Note that you must activate your environment before running any `agentc` commands!_

8. Start up a Couchbase instance.

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
       Capella instances in particular require a root certificate, which you can get by

   Once Couchbase instance is running, enable the following services on your Couchbase cluster:
    - Data, Query, Index: For storing and retrieving catalog items + logs.
    - Search: For retrieving catalog items using semantic search.
    - Analytics: For efficient processing of logs.

   This specific agent also uses the `travel-sample` bucket.
   You'll need to navigate to your instance's UI (for local instances, this is on http://localhost:8091) to install
   this sample bucket.

8. Create a `.env` file from the `.env.example` file and tweak this to your environment.

   ```bash
   cp .env.example .env
   vi .env
   ```












8. Initialize your Agent Catalog instance by ru

8. Make sure your Git repo is clean, and run `agentc index` to index your tools and prompts.
   Note that `tools` and `inputs` are _relative paths_ to the `tools` and `inputs` folder.

   ```bash
   # agentc index $PATH_TO_TOOLS_FOLDER $PATH_TO_THE_PROMPTS_FOLDER
   agentc index tools prompts
   ```

   The command will subsequently crawl the `tools` and `inputs` folder for tools and prompts.

   _Hint: if you've made changes but want to keep the same commit ID for the later "publish" step, use
   `git add $MY_FILES` followed by `git commit --amend`!_

9.



11. Publish your local agent catalog to your Couchbase instance with `agentc publish`.
    Your Couchbase instance details in the `.env` file will be used for authentication.
    Again, this specific starter agent uses the `travel-sample` bucket.

```bash
agentc publish tool prompt --bucket travel-sample
```

12. Start a prefect server and run your agent!

```bash
export PREFECT_API_URL=http://127.0.0.1:4200/api
prefect server start &
python agent.py
```

13. Let's now talk with our agent!
    I initiated three conversations: two "positive" and one "negative".
    The first positive case is given below:

```text
Agent: Please provide the names of the source and destination airports, so I can find
  their IATA codes for you.

User: Let's go to LAX. I'm in SFO.

Agent Tool Call: find_direct_routes_between_airports(
  {'argument_input': {'source_airport': 'SFO', 'dest_airport': 'LAX'}}
)

Agent Task Result: Direct routes found between SFO and LAX with the following airlines:
  AS, DL, UA, US, VX, WN, AA.

Agent: Your routes are: Direct routes found between SFO and LAX with the following airlines: AS, DL, UA, US,
  VX, WN, AA.

Agent: Do you want to continue? Please respond with 'yes' or 'no'.

User: no
```

The second positive case is given below:

```text
Agent: Please provide the names of the source and destination airports, so I can find
  their IATA codes for you.

User: I need to go to LAX from YNW

Agent Tool Call: find_direct_routes_between_airports(
  {'argument_input': {'source_airport': 'YNW', 'dest_airport': 'LAX'}}
)

Agent Tool Call: find_routes_with_one_layover(
  {'argument_input': {'source_airport': 'YNW', 'dest_airport': 'LAX'}}
)

Agent Task Result: I couldn't find any direct or one-layover routes from YNW to LAX. Could you
  please provide another source airport that is close to YNW?

User: SFO

Agent Tool Call: find_direct_routes_between_airports(
  {'argument_input': {'source_airport': 'SFO', 'dest_airport': 'LAX'}}
)

Agent Tool Call: find_routes_with_one_layover(
  {'argument_input': {'source_airport': 'SFO', 'dest_airport': 'LAX'}}
)

Agent: Your routes are: I found several direct routes from SFO to LAX:
   1. Airline: AS, From: SFO, To: LAX
   2. Airline: DL, From: SFO, To: LAX
   3. Airline: UA, From: SFO, To: LAX
   4. Airline: US, From: SFO, To: LAX
   5. Airline: VX, From: SFO, To: LAX
   6. Airline: WN, From: SFO, To: LAX
   7. Airline: AA, From: SFO, To: LAX

Additionally, there are routes with one layover:
1. Airlines: AI, CX, From: SFO, Layover: HKG, To: LAX
   2. Airlines: AI, AA, From: SFO, Layover: HKG, To: LAX
   3. Airlines: AI, DL, From: SFO, Layover: ICN, To: LAX
   4. Airlines: AI, KE, From: SFO, Layover: ICN, To: LAX
   5. Airlines: AI, OZ, From: SFO, Layover: ICN, To: LAX
   6. Airlines: AI, TG, From: SFO, Layover: ICN, To: LAX
   7. Airlines: AI, UA, From: SFO, Layover: ICN, To: LAX
   8. Airlines: AM, AS, From: SFO, Layover: ATL, To: LAX
   9. Airlines: AM, AZ, From: SFO, Layover: ATL, To: LAX
   10. Airlines: AM, CI, From: SFO, Layover: ATL, To: LAX

Agent: Do you want to continue? Please respond with 'yes' or 'no'.

User: no
```

The negative case is given below:

```text
Agent: Please provide the names of the source and destination airports, so I can find
  their IATA codes for you.

User: i want to go to Mars, I'm from Saturn

Agent: It seems like you're mentioning planets! For this task, I need the names of
  actual airports on Earth. Could you please provide the name of the source
  airport and the destination airport?

User: no

Error: The user did not provide valid source and destination airports, which are necessary to
  complete the task of returning IATA codes.
```

For some ideas on how to quantify the quality of your agent, see the `notebook.ipynb` file!
