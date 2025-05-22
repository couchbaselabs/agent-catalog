.. role:: python(code)
   :language: python

.. role:: sql(code)
   :language: sql

Agent Catalog: A Primer
=======================

Introduction
------------

The Agent Catalog project aims to enrich your agent development process by i) providing a consolidated view of tools
and prompts used by your agents and ii) enabling observability with our logging library + Couchbase.
In this short tutorial, we will:

1. Build a set of tools and prompts for a 3-agent application ;
2. Use these tools and prompts to realize the agent in LangGraph ; and
3. Perform some prompt engineering to improve our application using a Git-backed workflow.

We assume no prior LangGraph or Agent Catalog experience in this tutorial.
This application is available in full `here <https://github.com/couchbaselabs/agent-catalog/tree/master/examples/with_langgraph>`__.

Step #0: Defining a Smart Travel Application
--------------------------------------------

To start, let's explain the application we want to build.
We are interested in developing a chatbot that is able to use a structured knowledge base (Couchbase) to answer
routing-related questions.
*Agents* are actors with agency that interact with an environment and possibly other actors.
We use agents to realize the broad set of tasks representing these "routing-related" questions.
Specifically, in Figure 1 (below) we define an architecture of three agents to handle these questions:

1. "Front Desk" -- Purposed to interact with the user and the "Endpoint Finding" agent.
2. "Endpoint Finding" -- Purposed to translate the user's input into IATA airport codes and interact with the
   "Route Finding" agent.
3. "Route Finding" -- Purposed to find routes (using Couchbase queries) between the endpoints provided by the
   "Endpoint Finding" and to i) interact with the "Endpoint Finding" agent to provide new endpoints if no routes are
   found or ii) send the routes (or lack of routes) to the "Front Desk" agent to give back to the user.

.. mermaid::
    :title: 3-Agent Route Finding System
    :align: center
    :caption: **Figure 1**: The 3-agent system (a Front Desk agent, a Route Finding agent, and an Endpoint Finding
        agent) we will be working with.

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

To hold all of the code we will write in the following sections, we'll need a place to put everything.
Specifically, we'll need a Git repository and a Python environment.
Copy and paste the commands below to get started:

.. code-block:: ansi-shell-session

    $ git init
    $ python3 -m venv venv
    $ source venv/bin/activate
    $ pip install agentc[langchain,langgraph]

To initialize Agent Catalog, provide your Couchbase connection details and run ``agentc init``.
You can also save these to a ``.env`` file and ``agentc`` will read these values accordingly.

.. code-block:: ansi-shell-session

    $ export AGENT_CATALOG_CONN_STRING=...
    $ export AGENT_CATALOG_USERNAME=...
    $ export AGENT_CATALOG_PASSWORD=...
    $ export AGENT_CATALOG_BUCKET=...
    $ export AGENT_CATALOG_CONN_ROOT_CERTIFICATE=...
    $ agentc init


Step #1: Building Agent Tools and Prompts
-----------------------------------------

Building Our Agent Prompts
^^^^^^^^^^^^^^^^^^^^^^^^^^

Having defined the problem we want to solve, let's now detail the individual actions each agent should take.
Agents are realized by *prompting* large language models like GPT-4o.
In Agent Catalog, prompts are authored in YAML with (at a minimum) a name, a description, and content.
We give the prompt for our endpoint finding agent below:

.. code-block:: yaml

    record_kind: prompt
    name: endpoint_finding_node
    description: >
      All inputs required to assemble the endpoint-finding node.

    output:
      title: Endpoints
      description: The source and destination airports for a flight / route.
      type: object
      properties:
        source:
          type: string
          description: "The IATA code for the source airport."
        dest:
          type: string
          description: "The IATA code for the destination airport."
      required: [source, dest]

    content:
      agent_instructions: >
        Your task is to find the source and destination airports for a flight.
        The user will provide you with the source and destination cities.
        You need to find the IATA codes for the source and destination airports.
        Another agent will use these IATA codes to find a route between the two
        airports.
        If a route cannot be found, suggest alternate airports (preferring
        airports that are more likely to have routes between them).

      output_format_instructions: >
        Ensure that each IATA code is a string and is capitalized.

Note that our ``content`` field is an object with two objects: ``agent_instructions`` and
``output_format_instructions``.
The former describes directions the agent must take to find the source and destination airports while the latter
describes instructions for formatting its response.

.. note::

    Frameworks like CrewAI may possess their own set of templates with variables that must be bound (e.g.,
    ``instructions``, ``persona``, ``examples``, etc...).
    ``content`` can include any arbitrary collection of fields that can later be used to interface with any framework.
    To use our prebuilt LangGraph integration libraries, adding ``agent_instructions`` and
    ``output_format_instructions`` allows us (Agent Catalog) to properly map these fields to LangGraph's
    ``langgraph.prebuilt.create_react_agent``.

In addition to the ``name``, ``description``, and ``content`` fields, we also specify an ``output`` field in our prompt.
LLMs that support structured responses / guided decoding allow developers like us to make our applications more robust.
For our endpoint finding agent, we mandate that its output is an object with ``source`` and ``dest`` fields.
This output field is expressed in JSON schema (using YAML syntax).

Below, we give the prompt for our front desk agent.

.. code-block:: yaml

    record_kind: prompt
    name: front_desk_node
    description: >
      All inputs required to assemble the front-desk node.

    output:
      title: ResponseOrShouldContinue
      description: >
        The response to the user's input and whether (or not)
        the conversation should continue.
      type: object
      properties:
        is_last_step:
          type: boolean
          description: "Whether (or not) the conversation should continue."
        response:
          type: string
          description: "The response to the user's input."
        needs_clarification:
          type: boolean
          description: "Whether (or not) the response needs clarification."
      required: [ should_continue, response, needs_clarification ]

    content:
      agent_instructions:
        - >
          Your task is to respond to the user AND decide if the conversation
          should end based on the user's response.
          If you have any routes that have been given to by another agent,
          respond to the user in Markdown illustrating the routes.

        - >
          If the user asks for help with flight planning but there are no
          source and destination cities provided, set the
          'needs_clarification' field to True and provide a polite response.

        - >
          If the user asks / replies with anything not related to flight
          planning, set the 'is_last_step' field to True and
          'needs_clarification' to True.
          DO NOT continue the conversation if the user's input / response is
          not related to flight planning.
          For example, the following responses should end the conversation
          (set 'is_last_step' to True):
          - I need help with my hotel reservation. ==> is_last_step: True
          - Can you help me with my car rental? ==> is_last_step: True
          - I need recommendations for restaurants in the area.
            ==> is_last_step: True

        - >
          If the user wants to end the conversation, set the 'is_last_step'
          field to True and provide a polite response.
          For example:
          - Thanks! That's all I need. ==> is_last_step: True
          - I'm done for now. ==> is_last_step: True
          - That's all for today. ==> is_last_step: True

      output_format_instructions: >
        Be polite and professional in your responses.
        Err on the side of caution when deciding whether to continue the
        conversation.
        If you are unsure, it is better to **END** the conversation than
        to continue it.

The ``content.agent_instructions`` field for our front desk agent is a YAML list of four strings.
The practice of "prompt engineering" in the context of agents entails meticulously evolving this ``agent_instructions``
field.
As we will later see, prompt engineering is closely related with problem specification.
An ill-defined specification leads to sub-optimal performance, but it is unreasonable to ask for a well defined
specification upfront.
This process of prompt evolution needs to be seamless and provenance-respecting, which Agent Catalog enables.

Finally, we give the prompt for our route finding agent below:

.. code-block:: yaml

    record_kind: prompt
    name: route_finding_node
    description: >
      All inputs required to assemble the route-finding node.

    tools:
      - name: "find_direct_routes_between_airports"
      - query: "finding indirect flights (those with layovers)"
        limit: 2

    output:
      title: Routes
      description: >
        A list of a sequence of flights (source and destinations) that connect
        two airports.
      type: object
      properties:
        routes:
          type: array
          items:
            type: object
            properties:
              source:
                type: string
                description: "The IATA code for the source airport."
              dest:
                type: string
                description: "The IATA code for the destination airport."
            required: [ source, dest ]
        is_last_step:
          type: boolean
          description: >
            Whether the agent should continue to find routes between new source
            and destination cities.
      required: [ routes, is_last_step ]

    content:
      agent_instructions:
        - >
          Your task is to use the provided tools to find a route that connects
          the source and destination airports.
          You will be given the source and destination cities.
          You MUST use the provided tools.
          Use routes with fewer layovers (e.g., if a direct flight and a
          one-layover flight exists, choose the direct flight).
        - >
          If no routes exist, return an empty list.
          You will then be given new source and destination cities to find
          routes between.
          If you cannot find a route after the second attempt, set the
          `is_last_step` flag to True.

      output_format_instructions: >
        Ensure that each IATA code is a string and is capitalized for all
        routes returned.

Compared to our endpoint finding agent prompt and our front desk agent prompt, our route finding agent prompt possesses
an additional field: ``tools``.
Prompts in Agent Catalog optionally specify a set of **tools** (discussed in detail in the following section) to be
associated with.
The first tool, ``find_direct_routes_between_airports``, is specified directly by name.
The next two tools are specified indirecty with a semantically similar query string: "finding indirect flights (those
with layovers)".
If prompt authors are unaware of the full set of tools available to them (as is the case for large agent applications),
they can estimate the exact tools they need within the prompt itself.

Building Our Agent Tools
^^^^^^^^^^^^^^^^^^^^^^^^

Tools are the "hands" of agent systems, enabling agents to (essentially) invoke functions.
In practice, this dependency is inverted -- applications invoke functions that an agent "calls".
Consequently, these tools are typically defined within the application itself.

In Agent Catalog, there are four tool classes: Python tools, semantic search tools, SQL++ query tools, and HTTP
request tools.
Let's define the first tool, which is ``find_direct_routes_between_airports`` in SQL++.

.. code-block:: sql

    /*
    name: find_direct_routes_between_airports
    description: >
        Find a list of direct routes between two airports using source_airport
        and destination_airport.
    input:
        type: object
        properties:
          source_airport:
            type: string
          destination_airport:
            type: string

    secrets:
        - couchbase:
            conn_string: CB_CONN_STRING
            username: CB_USERNAME
            password: CB_PASSWORD
            # certificate: CB_CERTIFICATE
    */
    FROM
        `travel-sample`.inventory.route r
    WHERE
        r.sourceairport = $source_airport AND
        r.destinationairport = $destination_airport
    SELECT VALUE {
        "airlines"     : [ r.airline ],
        "layovers"     : [],
        "from_airport" : r.sourceairport,
        "to_airport"   : r.destinationairport
    }
    LIMIT
        10;

Tools require metadata to instruct our agent on the tool's use.
In SQL++ tools, this metadata is captured in








Step #1: Building a LangGraph Application
-----------------------------------------

.. tip::

    Feel free to skip this section if you already have your agent application.


Building our Agent Graph
^^^^^^^^^^^^^^^^^^^^^^^^

Let's now realize the graph above in Figure 1 (above).
We will build up the agents, state, and edges in the next step.

.. code-block:: python

    # We define these in the following steps!
    FrontDeskAgent = ...
    EndpointFindingAgent = ...
    RouteFindingAgent = ...
    State = ...
    out_front_desk_edge = ...
    out_route_finding_edge = ...

    # Create a workflow graph.
    workflow = langgraph.graph.StateGraph(State)
    workflow.add_node("front_desk_agent", FrontDeskAgent())
    workflow.add_node("endpoint_finding_agent", EndpointFindingAgent())
    workflow.add_node("route_finding_agent", RouteFindingAgent())
    workflow.set_entry_point("front_desk_agent")
    workflow.add_conditional_edges(
        "front_desk_agent",
        out_front_desk_edge,
        {
            "ENDPOINT_FINDING": "endpoint_finding_agent",
            "FRONT_DESK": "front_desk_agent",
            "END": langgraph.graph.END,
        },
    )
    workflow.add_edge("endpoint_finding_agent", "route_finding_agent")
    workflow.add_conditional_edges(
        "route_finding_agent",
        out_route_finding_edge,
        {"FRONT_DESK": "front_desk_agent", "ENDPOINT_FINDING": "endpoint_finding_agent"},
    )
    graph = workflow.compile()

Building Our Agent Actions: The Tools
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If large language models like GPT-4o are the brain of agent systems, *tools* are the arms.
Tools are, in their purest form, *functions* that are invoked by LLMs and executed by in an application's environment.
In Python LangGraph applications, tools are Python functions


Defining a Contract: The State
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Similar to how humans communicate, agents require some sort of contract before communicating.
In LangGraph, this contract exists in the form of a :python:`State` class.
Let's define our state class as such:

.. code-block:: python

    import typing
    import langchain_core.messages

    class State(typing.TypedDict):
        messages: list[langchain_core.messages.BaseMessage]
        is_last_step: bool
        needs_clarification: bool
        endpoints: typing.Optional[dict]
        routes: typing.Optional[list[dict]]

Our state class, defined as a typed dictionary, has the following attributes:

1. A ``messages`` field, used to hold the history for the current conversation / session.
   This field is standard across most LangGraph applications.
2. A ``is_last_step`` field, a control field used to signal to the terminating agent (in our case, the "Front Desk")
   that the current session should end.
   Similar to ``messages``, this field is standard across most LangGraph applications.
3. A ``needs_clarification`` field, primarily a control field used by the "Front Desk" agent to repeat the "Front Desk"
   agent code block.
4. An ``endpoints`` field, used to hold endpoints found by our "Endpoint Finding" agent.
5. A ``routes`` field, used to hold routes found by our "Route Finding" agent.

Defining Our Graph Nodes
^^^^^^^^^^^^^^^^^^^^^^^^

The "nodes" in LangGraph, similar to other vertex-centric paradigms, are our pièce de résistance.
Nodes in LangGraph are defined as functions (or more generally, objects that implement the :python:`__call__` method)
that accept an instance of :python:`State` and return a (potentially modified) instance of the same input
:python:`State` [#]_.
Broadly speaking, nodes are where our calls to LLMs and tools occur.
In this tutorial, these LLM calls are managed using the ReAct paradigm (implemented in
:python:`langgraph.prebuilt.create_react_agent`).

To start, let's define the function class associated with our route finding agent:

.. code-block:: python

    import langchain_openai
    import langgraph.prebuilt

    chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)
    agent = langgraph.prebuilt.create_react_agent(model=chat_model)

.. [#] LangGraph nodes may also return :python:`Command` instances which contain information about where the outgoing
       :python:`State` instance should be forward to, but for this tutorial we will not use this paradigm.


Defining Our Graph Edges
^^^^^^^^^^^^^^^^^^^^^^^^

In LangGraph, edges are defined using functions that accept a :python:`State` instance (defined previously) and return
the name of the next node that will handle the current state.
As illustrated in Figure 1 (above, repeated directly below for reference), there are seven edges we need to define:

.. mermaid::
    :title: 3-Agent Route Finding System
    :align: center
    :caption: **Figure 1** (duplicate): The 3-agent system (a Front Desk agent, a Route Finding agent, and an Endpoint
        Finding agent) we will be working with.

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

1. The edge from ``__start__`` to ``front_desk_agent`` denotes that our graph starts with our "Front Desk" agent.
   This edge is constructed using the line:

   .. code-block:: python

        workflow.set_entry_point("front_desk_agent")

2. The solid edge from ``endpoint_finding_agent`` to ``route_finding_agent`` denotes that the "Endpoint Finding" agent
   will unconditionally forward its output to the "Route Finding" agent.
   This edge is constructed using the line:

   .. code-block:: python

        workflow.add_edge("endpoint_finding_agent", "route_finding_agent")

3. The dashed edges


Step #2: Adding Agent Catalog
-----------------------------

Step #3: Versioning and Improving Our Application
-------------------------------------------------





