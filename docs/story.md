# Why Rosetta?

Rosetta is an open-source Python package that provides a foundation for building agents using metrics-driven
development. It is not just a tool/prompt catalog, but a framework that integrates with agent applications in two main
areas: i) tool / prompt serving and ii) auditing. The purpose of this document is to provide a story of how Rosetta
helps your agent development.

## Building Agent v0.0.1

From 0 to 1, let's build a ticket labeling agent. Our "AI stack" will be:

1. ControlFlow (our agent building framework);
2. Couchbase (to hold our data, to cache conversations, and to provide private LLM access); and
3. FastAPI (for other applications to interact with our agent through REST).

Our first step is to `git clone` the barebones sample agent from the `rosetta-example` repository, which already has
this stack in place. We will create a new branch with `git checkout -b ticket-labeling-agent` and modify this agent
to fit our use case.

### Building Tasks for Agent v0.0.1

As prescribed by agent frameworks like ControlFlow and CrewAI, we will need to break our agent into _tasks_. This
agent will consist of the following tasks:

1. a task to fetch descriptive information about a ticket,
2. a task to assess the fetched information and determine whether more ticket info needs to be added,
3. a task to fetch semantically similar labels to the information fetched in the first and second task,
4. a task to generate and persist labels for the ticket itself if there are no accurate labels from the third task, and
5. a task to appropriately label the ticket given the candidate labels in tasks 3 and 4.

The general flow of our agent will be as follows (where `T_n` represents the `n`th task):

```text
   ┌────────┐        ┌─────────────────┐
   │        │        │                 │
┌──▼──┐  ┌──┴──┐  ┌──┴──┐  ┌─────┐  ┌──▼──┐
│     │  │     │  │     │  │     │  │     │
│ T_1 ┼──► T_2 ┼──► T_3 ┼──► T_4 ┼──► T_5 │
│     │  │     │  │     │  │     │  │     │
└─────┘  └─────┘  └─────┘  └─────┘  └─────┘
```

Note that each of these tasks require some level of "intelligence" to be performed correctly, and each task requires
some tool or function to be executed. We will use Rosetta to a) help build our tools, b) help build our prompts, and
c) audit our agent's actions. Item c) is especially important, as we want to use these logs to guide the development
of agent v0.0.2.

### Building Prompts for Agent v0.0.1

Let's write the prompts for our first task: fetching descriptive information about a ticket. Using the template given
in the `prompts` directory, we will duplicate the template and create a file called `prompts/describe_ticket.prompt`.
We will fill out the template with the necessary information and have an artifact that looks like this:

```text
---
record_kind: raw_prompt

name: describe_ticket

description: >
    Instructions on how to retrieve descriptive information about a ticket.

tools:
  - query: "finding ticket descriptions by ID"
    limit: 1
  - query: "finding ticket labels by ID"
    limit: 1
---
Goal:
Your goal is to find enough descriptive information to label a ticket.

Instructions:
If this is your first attempt, you MUST find the ticket's description by its ID.
If this is your second attempt, you MUST find the ticket's labels by its ID.
```

Note that we haven't defined the tools yet, _but_ we know that we will need tools to find the ticket's description and
labels. Rosetta's semantic tool search enables users to find tools that match tool descriptions rather than rigid tool
names (if you have existing tools, you can forgo the semantic search altogether).

Let's now finish the remaining four prompts, which we will name `prompts/should_fetch_more_info.prompt`,
`prompts/find_similar_labels.prompt`, `prompts/generate_labels_if_necessary.prompt`, and `prompts/label_ticket.prompt`.

```text
---
record_kind: raw_prompt

name: should_fetch_more_info

description: >
    Instructions on how to determine whether more ticket info needs to be added.
---
Goal:
Your goal is to determine whether you have enough information to label a ticket.
If you do not have enough information, you must return True.
If you have enough information, you must return False.
Do not explain your answer.
```

```text
---
record_kind: raw_prompt

name: find_similar_labels

description: >
    Instructions on how to fetch semantically similar labels using a ticket's description.

tools:
  - query: "finding labels using a description"
    limit: 1
---
Goal:
Your goal is to find semantically similar labels to a ticket's descriptive info.
Do NOT generate labels, your goal is to use a tool to find similar labels and subsequently choose 1-3 appropriate
labels.
If you cannot find any labels, return an empty list.
```

```text
---
record_kind: raw_prompt

name: generate_labels_if_necessary

description: >
    Instructions on how to generate and persist labels for a ticket if there are no accurate labels.

tools:
  - query: "adding a new label to the label store"
    limit: 1
  - query: "generating a vector for a label"
    limit: 1
  - query: "finding labels using a description"
    limit: 1
---
Goal:
Your goal is to generate 1-3 labels for a ticket.
Do NOT generate labels that already exist in the label store.
Check whether or not the labels exist in the label store using a tool.
```

```text
---
record_kind: raw_prompt

name: label_ticket

description: >
    Instructions on how to label a ticket given a set of candidate labels.

tools:
  - query: "attach a label to a ticket"
    limit: 1
---
Goal:
Your goal is to assign 3-5 labels to a ticket.
Prefer diverse labels over similar labels.
```

### Building Tools for Agent v0.0.1

With our prompts in place, let's now build the tools required by our prompts. We can use the templates in the `tools`
directory to create tools to satisfy the requirements of our prompts. For convenience, we enumerate all required tools
below:

1. a tool to find ticket descriptions by ID,
2. a tool to find ticket labels by ID,
3. a tool to find labels using a description,
4. a tool to add a new label to the label store, and
5. a tool to attach a label to a ticket.

Because Rosetta integrates nicely with Couchbase, we will use Couchbase to store our tickets, labels, and the ticket-to-
label mapping (a process that is out of the scope of this article, but is traditional database design that Couchbase
enables). For our specific problem, we will consider the following Couchbase collections with the following schemas
(in the bucket `Rosetta` and the scope `Support`):

```text
Rosetta.Support.Tickets(`Issue key` STRING, ...)
Rosetta.Support.Labels (label STRING, vec: ARRAY[FLOAT])
Rosetta.Support.RecommendedLabels (ticket_id STRING, label STRING)
```

For now, in addition to the five tools above, we will use a sixth tool to generate the vector that we will attach to
the label. This is also a good chance to illustrate how Python tools are recognized by Rosetta:

```python
import sentence_transformers
import rosetta

@rosetta.tool
def get_vector_for_label(label: str) -> list[float]:
    """Generating a vector for a label, for use before applying this to a vector index."""
    model = sentence_transformers.SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")
    label_vector = model.encode(label)
    return label_vector
```

The code above exists in a file called `tools/generate_vector_for_label.py`. Note that all Rosetta requires is that you
annotate your existing Python code with @rosetta.tool._In the future, this tool will be deprecated with Vulcan._ In both
cases, the end result is a vector index managed by the Couchbase Search Service which we can subsequently perform
semantic search over. Our resultant index is named `Rosetta.Support.LabelsIndex` and the embedding model used was
`sentence-transformers/all-MiniLM-L12-v2` (we'll need both of these for later).

Now, let us build the tools required by our prompts with our Couchbase collections in mind. Tools #1 and #2 are
straightforward SQL queries (a lookup by the primary key). We author these tools below and save them as
`tools/find_ticket_description_by_id.sqlpp` and `tools/find_ticket_labels_by_id.sqlpp`, respectively:

```sql
/*
name: find_ticket_description_by_id

description: >
    A tool to find a ticket's description by its issue key.

input: >
    {
       "type": "object",
       "properties": {
          "issue_key": {
                "type": "string"
          }
       }
    }

output: >
    {
       "type": "object",
       "properties": {
          "Description": {
                "type": "string"
          }
       }
    }

secrets:
    - couchbase:
        conn_string: CB_CONN_STRING
        username: CB_USERNAME
        password: CB_PASSWORD
*/
SELECT t.Description
FROM Rosetta.Support.Tickets AS t
WHERE t.`Issue key` = $issue_key;
```

```sql
/*
name: find_ticket_labels_by_id

description: >
    A tool to find a ticket's (pre-existing) labels by its issue key.

input: >
    {
       "type": "object",
       "properties": {
          "issue_key": {
                "type": "string"
          }
       }
    }

output: >
    {
       "type": "object",
       "properties": {
          "Labels": {
                "type": "string"
          }
       }
    }

secrets:
    - couchbase:
        conn_string: CB_CONN_STRING
        username: CB_USERNAME
        password: CB_PASSWORD
 */
SELECT t.Labels AS labels
FROM Rosetta.Support.Tickets AS t
WHERE t.`Issue key` = $issue_key;
```

Tool #3 is a bit more complex, as it requires a semantic search over our labels. Luckily, Rosetta allows us to define
semantic search with a YAML file! We will save this tool as `tools/find_labels_using_description.yaml`:

```yaml
record_kind: semantic_search

name: find_labels_using_description

description: >
  Find labels using some collection of text (description).

input: >
  {
    "type": "object",
    "properties": {
      "description": {
        "type": "string"
      }
    }
  }

secrets:
  - couchbase:
      conn_string: CB_CONN_STRING
      username: CB_USERNAME
      password: CB_PASSWORD

vector_search:
  bucket: Rosetta
  scope: Support
  collection: Labels
  index: LabelsIndex
  vector_field: vec
  text_field: label
  embedding_model: sentence-transformers/all-MiniLM-L12-v2
```

Tools #4 and #5 are also straightforward SQL queries. We (again) author these tools below with iQ (TODO) and save them
as `tools/add_new_label_to_label_store.sqlpp` and `tools/attach_label_to_ticket.sqlpp`, respectively:

```sql
/*
name: add_new_label_to_label_store

description: >
    A tool to add a new label to the label store.

input: >
    {
       "type": "object",
       "properties": {
          "label": {
             "type": "string"
          },
          "vec": {
             "type": "array",
             "items": {
                "type": "number"
             }
          }
       }
    }

output: >
    {
       "type": "object",
       "properties": {
       }
    }

secrets:
    - couchbase:
        conn_string: CB_CONN_STRING
        username: CB_USERNAME
        password: CB_PASSWORD
*/
INSERT INTO Rosetta.Support.Labels (KEY, VALUE)
VALUES ($label, { "label" : $label, "vec": $vec });
```

```sql
/*
name: attach_label_to_ticket

description: >
    A tool to associate a new label with an existing ticket.

input: >
    {
       "type": "object",
       "properties": {
          "label": {
             "type": "string"
          },
          "issue_key": {
             "type": "string"
          }
       }
    }

output: >
    {
       "type": "object",
       "properties": {
       }
    }

secrets:
    - couchbase:
        conn_string: CB_CONN_STRING
        username: CB_USERNAME
        password: CB_PASSWORD
*/
INSERT INTO Rosetta.Support.RecommendedLabels (KEY, VALUE)
VALUES (UUID(), { "label" : $label, "issue_key": $issue_key });
```

### Piecing Everything Together
We have the pieces in place to build an agent with ControlFlow and Rosetta. The barebones sample agent has a set of
helper functions that we can use to glue these pieces together more efficiently. We will modify the `agent.py` file
to slot in our prompts into a flow. The end result is a Python file that looks like this:
```python
import controlflow
import controlflow.tools
import controlflow.events
import controlflow.orchestration
import langchain_openai
import os
import uuid
import queue
import rosetta
import rosetta.provider
import rosetta.auditor
import rosetta.langchain

from utils import TaskFactory

provider = rosetta.Provider(
    decorator=lambda t: controlflow.tools.Tool.from_function(t.func),
    secrets={
        "CB_CONN_STRING": os.getenv("CB_CONN_STRING"),
        "CB_USERNAME": os.getenv("CB_USERNAME"),
        "CB_PASSWORD": os.getenv("CB_PASSWORD"),
    },
)
auditor = rosetta.auditor.Auditor(llm_name="gpt-4o")
chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)


def run_flow(thread_id: str, ticket_queue: queue.Queue):
    support_agent = controlflow.Agent(
        name="Support Agent",
        model=rosetta.langchain.audit(chat_model, session=thread_id, auditor=auditor),
    )
    flow = controlflow.Flow(default_agent=support_agent, thread_id=thread_id)

    # Below, we have a helper class that removes some of the boilerplate for using Rosetta + ControlFlow.
    task_factory = TaskFactory(
        provider=provider,
        auditor=auditor,
        session=thread_id,
        agent=support_agent
    )

    while not ticket_queue.empty():
        ticket = ticket_queue.get()
        is_describing = True
        describe_ticket = task_factory.build(prompt_name="describe_ticket", context={"issue_key": ticket})
        while is_describing:
            should_fetch_more_info = task_factory.build(
                prompt_name="should_fetch_more_info",
                context={"description": describe_ticket}
            )
            controlflow.run_tasks([describe_ticket], flow=flow)
            if not should_fetch_more_info.result:
                is_describing = False
            else:
                describe_ticket = task_factory.build(prompt_name="describe_ticket", context={"issue_key": ticket})

        find_similar_labels = task_factory.build(
            prompt_name="find_similar_labels",
            context={"description": describe_ticket}
        )
        generate_labels_if_necessary = task_factory.build(
            prompt_name="generate_labels_if_necessary",
            context={"labels": find_similar_labels}
        )
        label_ticket = task_factory.build(prompt_name="label_ticket", context={"labels": generate_labels_if_necessary})
        controlflow.run_tasks([label_ticket], flow=flow)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Label a list of tickets given their issue key.')
    parser.add_argument(
        'tickets',
        metavar='ISSUE_KEY',
        type=str,
        nargs='+',
        help='A list of ticket issue keys.'
    )
    args = parser.parse_args()

    _ticket_queue = queue.Queue()
    for _ticket in args.tickets:
        _ticket_queue.put(_ticket)
    run_flow(uuid.uuid4().hex, _ticket_queue)
```

The last part of this process is to use the `rosetta` CLI to index our tools and prompts, and to publish them to our
Couchbase instance. We will use the following commands to do so:

```bash
git add prompts tools
git commit -m "feat: add prompts and tools for ticket labeling agent"

rosetta index tools --kind tool
rosetta index prompts --kind prompt
rosetta publish --kind all --bucket Rosetta
```

Note the use of git to version our tools and prompts. Instead of versioning tools and prompts individually, these tools
and prompts are versioned alongside the agent itself.

## Assessing Agent v0.0.1
Now let's actually run our agent. We run our agent with `python agent_flow.py CCBSE-968` and get the following output:
```text
╭── Agent: Support Agent ──────────────────────────────────────────────────────╮
│                                                                              │
│  ✅ Tool call: "find_ticket_description_by_id"                               │
│                                                                              │
│     Tool args: {'argument_input': {'issue_key': 'CCBSE-968'}}                │
│                                                                              │
│     Tool result: {"Description":"It seems the read/write/compute units       │
│     graph is not loading with any data even though there are certain         │
│     read/write                                                               │
│     operations.\n\n\n!image-2023-04-17-08-54-58-865.png|width=958,height=4…  │
│                                                                              │
╰────────────────────────────────────────────────────────────────  3:57:48 PM ─╯
╭─ Agent: Support Agent ───────────────────────────────────────────────────────╮
│                                                                              │
│  ✅ Tool call: "mark_task_e0d8b728_successful"                               │
│                                                                              │
│     Tool args: {'result': 'It seems the read/write/compute units graph is    │
│     not loading with any data even though there are certain read/write       │
│     operations.\n\n\n!image-2023-04-17-08-54-58-865.png|width=958,height=4…  │
│                                                                              │
│     Tool result: Task #e0d8b728 ("                                           │
│     Goal:                                                                    │
│     Your goal is to find enough descriptive inf...") marked successful.      │
│                                                                              │
╰────────────────────────────────────────────────────────────────  3:57:50 PM ─╯
│                                                                              │
│  Based on the ticket description, here are the potential labels:             │
│                                                                              │
│   1 Graph Issue                                                              │
│   2 Data Loading Problem                                                     │
│   3 Read/Write Operations                                                    │
│   4 Compute Units                                                            │
│   5 Visualization Bug                                                        │
│                                                                              │
│  I will now attach these labels to the ticket.                               │
│                                                                              │
│                                                                              │
│  ✅ Tool call: "attach_label_to_ticket"                                      │
│                                                                              │
│     Tool args: {'argument_input': {'label': 'Graph Issue', 'issue_key':      │
│     'CCBSE-968'}}                                                            │
│                                                                              │
│     Tool result:                                                             │
│  ✅ Tool call: "attach_label_to_ticket"                                      │
│                                                                              │
│     Tool args: {'argument_input': {'label': 'Data Loading Problem',          │
│     'issue_key': 'CCBSE-968'}}                                               │
│                                                                              │
│     Tool result:                                                             │
│  ✅ Tool call: "attach_label_to_ticket"                                      │
│                                                                              │
│     Tool args: {'argument_input': {'label': 'Read/Write Operations',         │
│     'issue_key': 'CCBSE-968'}}                                               │
│                                                                              │
│     Tool result:                                                             │
│  ✅ Tool call: "attach_label_to_ticket"                                      │
│                                                                              │
│     Tool args: {'argument_input': {'label': 'Compute Units', 'issue_key':    │
│     'CCBSE-968'}}                                                            │
│                                                                              │
│     Tool result:                                                             │
│  ✅ Tool call: "attach_label_to_ticket"                                      │
│                                                                              │
│     Tool args: {'argument_input': {'label': 'Visualization Bug',             │
│     'issue_key': 'CCBSE-968'}}                                               │
│                                                                              │
│     Tool result:                                                             │
│                                                                              │
╰────────────────────────────────────────────────────────────────  3:57:59 PM ─╯
╭─ Agent: Support Agent ───────────────────────────────────────────────────────╮
│                                                                              │
│  ✅ Tool call: "mark_task_4db3f04d_successful"                               │
│                                                                              │
│     Tool args: {'result': 'Labels assigned: Graph Issue, Data Loading        │
│     Problem, Read/Write Operations, Compute Units, Visualization Bug'}       │
│                                                                              │
│     Tool result: Task #4db3f04d ("                                           │
│     Goal:                                                                    │
│     Your goal is to assign 3-5 labels to a tick...") marked successful.      │
│                                                                              │
╰────────────────────────────────────────────────────────────────  3:58:00 PM ─╯
```

Putting aside the quality of the generated labels, (we'll get there in a bit), let's see what our agent has gotten
correct by glancing at this ControlFlow output:
- The agent successfully fetched the ticket description for `CCBSE-968`.
- The agent has successfully labeled the ticket with the labels `Graph Issue`, `Data Loading Problem`, `Read/Write
  Operations`, `Compute Units`, and `Visualization Bug`.

MORE TO COME :-)

## Building Agent v0.0.2
We have the logs from the previous run, and we want to make sure that our agent isn't ........



