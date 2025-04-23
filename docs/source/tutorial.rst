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

1. Build a 3-agent application using LangGraph ;
2. Integrate Agent Catalog into our existing application ; and
3. Perform some prompt engineering to improve our application using a Git-backed workflow.

We assume no prior LangGraph or Agent Catalog experience in this tutorial.
This application is available in full `here <https://github.com/couchbaselabs/agent-catalog/tree/master/examples/with_langgraph>`__.

Step #1: Building a LangGraph Application
-----------------------------------------

.. tip::

    Feel free to skip this section if you already have your agent application.

To start, let's explain the application we want to build.
We are interested in developing a chatbot that is able to use a structured knowledge base (Couchbase) to answer
routing-related questions.
*Agents* are actors with agency that interact with an environment and possibly other actors.
We use agents to realize the broad set of tasks representing these "routing-related" questions.
Specifically, in Figure 1 (below) we define an architecture of three agents to handle these questions:

1. "Front Desk" -- Purposed to interact with the user and the "Endpoint Finding" agent.
2. "Endpoint Finding" -- Purposed to translate the user's input into IATA airport codes and interact with the
   "Route Finding" agent.
3. "Route Finding" -- Purposed to find routes using Couchbase tools between the endpoints provided by the
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


Defining a Contract: The State
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Similar to how humans communicate, agents require some sort of contract before communicating.
As an example, you *typically* don't start a conversation with your barista by summarizing the intricacies of bread
tabs (at least where we are from :-)).
In LangGraph, this contract exists in the form of a ``State`` class.
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



Defining Our Graph Edges
^^^^^^^^^^^^^^^^^^^^^^^^

In LangGraph, edges are defined using functions that accept a ``State`` instance (defined previously) and return the
name of the next node that will handle the current state.
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




