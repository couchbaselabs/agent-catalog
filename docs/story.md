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
in the `prompts` directory, we will duplicate the template and create a file called `prompts/describe_ticket.yaml`.
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

Let's now finish the remaining four prompts, which we will name `prompts/should_fetch_more_info.yaml`,
`prompts/find_similar_labels.yaml`, `prompts/generate_labels_if_necessary.yaml`, and `prompts/label_ticket.yaml`.

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

```sql
Rosetta
.
Support
.
Tickets
(ticket_id STRING, ...)
Rosetta.Support.Labels (label STRING, vec: ARRAY[FLOAT])
Rosetta.Support.RecommendedLabels (ticket_id STRING, label STRING)
```

Using Vulcan, we can automatically attach embeddings to our labels (TODO). The end result is a vector index managed by
the Couchbase Search Service which we can subsequently perform semantic search over. Our resultant index is
named `Rosetta.Support.LabelsVectorIndex` and the embedding model used was `sentence-transformers/all-MiniLM-L12-v2`
(we'll need both of these for later).

Now, let us build the tools required by our prompts with our Couchbase collections in mind. Tools #1 and #2 are
straightforward SQL queries (a lookup by the primary key). We author these tools below with iQ (TODO) and save them as
`tools/find_ticket_description_by_id.sqlpp` and `tools/find_ticket_labels_by_id.sqlpp`, respectively:

```sql
/*
name: find_ticket_description_by_id

description: >
    A tool to find a ticket's description by its ID.

input: >
    {
       "type": "object",
       "properties": {
          "ticket_id": {
                "type": "string"
          }
       }
    }

output: >
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
*/
SELECT t.description
FROM Rosetta.Support.Tickets AS t
WHERE t.ticket_id = $ticket_id;
```

```sql
/*
name: find_ticket_labels_by_id

description: >
    A tool to find a ticket's (pre-existing) labels by its ID.

input: >
    {
       "type": "object",
       "properties": {
          "ticket_id": {
                "type": "string"
          }
       }
    }

output: >
    {
       "type": "object",
       "properties": {
          "label": {
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
SELECT t.label
FROM Rosetta.Support.Tickets AS t
WHERE t.ticket_id = $ticket_id;
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
  index: LabelsVectorIndex
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
VALUES ($label, { "label" : $label, "vec": $vec }) );
```

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
          "ticket_id": {
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
VALUES (UUID(), { "label" : $label, "ticket_id": $ticket_id }) );
```

### Piecing Everything Together
We have the pieces in place to build an agent with ControlFlow and Rosetta. The barebones sample agent has a set of
helper functions that we can use to glue these pieces together more efficiently. We will modify the `agent_flow.py` file
to slot in our prompts into a flow. The end result is a Python file that looks like this:
```python
import controlflow
import controlflow.tools
import controlflow.events
import controlflow.orchestration
import dotenv
import langchain_openai
import os
import uuid
import pydantic
import queue
import rosetta
import rosetta.provider
import rosetta.auditor
import rosetta.langchain
import typing

# Load our OPENAI_API_KEY.
dotenv.load_dotenv()

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
    travel_agent = controlflow.Agent(
        name="Couchbase Travel Agent",
        model=rosetta.langchain.audit(chat_model, session=thread_id, auditor=auditor),
    )
    flow = controlflow.Flow(default_agent=travel_agent, thread_id=thread_id)

    # Below, we have a helper function which will fetch the versioned prompts + tools from the catalog.
    def Task(prompt_name: str, **kwargs) -> controlflow.Task:
        prompt: rosetta.provider.Prompt = provider.get_prompt_for(name=prompt_name)
        if prompt is None:
            raise RuntimeError(f"Prompt not found with the name {prompt_name}!")
        tools = prompt.tools + [talk_to_user] if prompt.tools is not None else [talk_to_user]
        return controlflow.Task(objective=prompt.prompt, tools=tools, **kwargs)

    for ticket in ticket_queue:
        is_describing = True
        describe_ticket = Task(prompt_name="describe_ticket", context={"ticket_id": ticket})
        while is_describing:
            should_fetch_more_info = Task(prompt_name="should_fetch_more_info", context={"description": describe_ticket})
            controlflow.run_tasks([describe_ticket], flow=flow, handlers=[audit_task_transition])
            if not should_fetch_more_info.result:
                is_describing = False
            else:
                describe_ticket = Task(prompt_name="describe_ticket", context={"ticket_id": ticket})

        find_similar_labels = Task(prompt_name="find_similar_labels", context={"description": describe_ticket})
        generate_labels_if_necessary = Task(prompt_name="generate_labels_if_necessary", context={"labels": find_similar_labels})
        label_ticket = Task(prompt_name="label_ticket", context={"labels": generate_labels_if_necessary})
        controlflow.run_tasks([label_ticket], flow=flow, handlers=[audit_task_transition])

if __name__ == '__main__':
    import sys
    ticket_queue = sys.argv[2:]
    run_flow(uuid.uuid4().hex, ticket_queue)
```

The last part is to use the `rosetta` CLI to index our tools and prompts, and to publish them to our Couchbase instance.
We will use the following commands to do so:

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
Now let's actually run our agent. We run our agent with `python agent_flow.py ticket1 ticket2 ticket3` and observe that
something is happening, but we're not sure if it's working as intended.

## Building Agent v0.0.2
We have the logs from the previous run, and we want to make sure that our agent isn't ........



