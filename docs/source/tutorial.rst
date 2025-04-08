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
This application is available in full `here <TODO REPLACE ME WITH LINK>`__.

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

Defining a Contract: The State
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Similar to how humans communicate, agents require... (TODO)





Step #2: Adding Agent Catalog
-----------------------------

Step #3: Versioning and Improving Our Application
-------------------------------------------------




