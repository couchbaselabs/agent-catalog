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
2. Use these tools and prompts to realize each agent in LangGraph ; and
3. Perform some prompt engineering to improve our application using a Git-backed workflow.

We assume no prior LangGraph or Agent Catalog experience in this tutorial.
This application is available in full `here <https://github.com/couchbaselabs/agent-catalog/tree/master/examples/with_langgraph>`__.

.. tip::

    In a hurry?
    Check out our notebook example `here <https://github.com/couchbaselabs/agent-catalog/tree/master/examples/with_notebook>`__
    for a slim two-agent network that uses Agent Catalog and LangGraph.

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
    $ agentc init --add-hook-for tools --add-hook-for prompts

The ``--add-hook-for`` option allows us to integrate with :command:`git` as a post-commit hook.
Here, we will focus on ``tools`` and ``prompts`` as directories.


Step #1: Building Agent Tools and Prompts
-----------------------------------------

Building Our Agent Prompts
^^^^^^^^^^^^^^^^^^^^^^^^^^

Having defined the problem we want to solve, let's now detail the individual actions each agent should take.
Agents are realized by *prompting* large language models like GPT-4o.
In Agent Catalog, prompts are authored in YAML with (at a minimum) a name, a description, and content.
We describe the prompt for each agent below.

.. dropdown:: Front Desk Agent Prompt

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
            - Be polite!

          output_format_instructions: >
            Be polite and professional in your responses.
            Err on the side of caution when deciding whether to continue the
            conversation.
            If you are unsure, it is better to **END** the conversation than
            to continue it.

    Note that our ``content`` field is an object with two objects: ``agent_instructions`` and
    ``output_format_instructions``.
    The former is a YAML list of four strings while the latter describes instructions for formatting its response.
    The practice of "prompt engineering" in the context of agents entails meticulously evolving this
    ``agent_instructions`` field.
    As we will later see, prompt engineering is closely related with problem specification.
    An ill-defined specification leads to sub-optimal performance, but it is unreasonable to ask for a well defined
    specification upfront.
    This process of prompt evolution needs to be seamless and provenance-respecting, which Agent Catalog enables.

    .. note::

        Frameworks like CrewAI may possess their own set of templates with variables that must be bound (e.g.,
        ``instructions``, ``persona``, ``examples``, etc...).
        ``content`` can include any arbitrary collection of fields that can later be used to interface with any
        framework.
        To use our prebuilt LangGraph integration libraries, adding ``agent_instructions`` and
        ``output_format_instructions`` allows us (Agent Catalog) to properly map these fields to LangGraph's
        ``langgraph.prebuilt.create_react_agent``.

    In addition to the ``name``, ``description``, and ``content`` fields, we also specify an ``output`` field in our
    prompt.
    LLMs that support structured responses / guided decoding allow developers like us to make our applications more
    robust.
    For our front desk agent, we mandate that its output contain a) a flag denoting whether or not the conversation
    should end, b) the response the agent should give (if any), and c) a flag denoting whether the agent must ask the
    user for more clarification.
    This output field is expressed in JSON schema (using YAML).

.. dropdown:: Endpoint Finding Agent Prompt

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

    Again, our ``content`` field is an object with two objects: ``agent_instructions`` and
    ``output_format_instructions``.
    The former describes directions the agent must take to find the source and destination airports.
    Finally, for our endpoint finding agent, we mandate that its output is an object with ``source`` and ``dest``
    fields.

.. dropdown:: Route Finding Agent Prompt

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

    Compared to our endpoint finding agent prompt and our front desk agent prompt, our route finding agent prompt
    possesses an additional field: ``tools``.
    Prompts in Agent Catalog optionally specify a set of **tools** (discussed in detail in the following section) to be
    associated with.
    The first tool, ``find_direct_routes_between_airports``, is specified directly by name.
    The next two tools are specified indirecty with a semantically similar query string: "finding indirect flights
    those with layovers)".
    If prompt authors are unaware of the full set of tools available to them (as is the case for large agent
    applications), they can estimate the exact tools they need within the prompt itself.

Building Our Agent Tools
^^^^^^^^^^^^^^^^^^^^^^^^

Tools are the "hands" of agent systems, enabling agents to (essentially) invoke functions.
In practice, this dependency is inverted -- applications invoke functions that an agent "calls".
Consequently, these tools are typically defined within the application itself.
In Agent Catalog, there are four tool classes: Python tools, semantic search tools, SQL++ query tools, and HTTP
request tools.
Below, we describe each of our tools.

.. dropdown:: Find Direct Routes Tool (SQL++)

    .. code-block::

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

    .. note::

        Note the use of named parameters ``$source_airport`` and ``$destination_airport`` in the SQL++ query itself.

    Tools require metadata to instruct our agent on the tool's use.
    In SQL++ tools, this metadata is captured in a multi-line comment containing a YAML block with the ``name``,
    ``description``, an ``input`` type and a ``secrets`` block.

    ``name`` and ``description`` are self-explanatory (these fields refer to the same concepts from our prompts).
    ``input`` describes the named parameters used by the SQL++ query.
    This description is expressed in JSON schema (using YAML).
    For this tool, the named parameters ``$source_airport`` and ``$destination_airport`` correspond to the
    ``source_airport`` and ``destination_airport`` string fields described in ``input``.
    The ``couchbase`` object inside the ``secrets`` list describes the keys that correspond to the connection details
    used to execute the query.
    In most cases, you shouldn't need to modify this field from the template -- you'll just need to make sure that
    ``CB_CONN_STRING``, ``CB_USERNAME``, and ``CB_PASSWORD`` are environment variables that are set.

    .. important::

        ``CB_CONN_STRING``, ``CB_USERNAME``, and ``CB_PASSWORD`` are distinct from ``AGENT_CATALOG_CONN_STRING``,
        ``AGENT_CATALOG_USERNAME``, and ``AGENT_CATALOG_PASSWORD``!
        In this example, you'll need to set both (even if Agent Catalog and the travel sample reside in the same
        cluster).

.. dropdown:: Find Indirect Routes Tools (Python)

    We could describe the remaining tools using the SQL++ tool format, but for teaching purposes we will author the
    remaining tools in Python.

    .. code-block:: python

        cluster = couchbase.cluster.Cluster(
            os.getenv("CB_CONN_STRING"),
            couchbase.options.ClusterOptions(
                authenticator=couchbase.auth.PasswordAuthenticator(
                    username=os.getenv("CB_USERNAME"),
                    password=os.getenv("CB_PASSWORD"),
                )
            ),
        )

        @agentc.catalog.tool
        def find_one_layover_flights(
            source_airport: str,
            destination_airport: str,
        ) -> list[dict]:
            """Find all one-layover (indirect) flights between two airports."""
            query = cluster.query(
                """
                    FROM
                        `travel-sample`.inventory.route r1,
                        `travel-sample`.inventory.route r2
                    WHERE
                        r1.sourceairport = $source_airport AND
                        r1.destinationairport = r2.sourceairport AND
                        r2.destinationairport = $destination_airport
                    SELECT VALUE {
                        "airlines"     : [r1.airline, r2.airline],
                        "layovers"     : [r1.destinationairport],
                        "from_airport" : r1.sourceairport,
                        "to_airport"   : r2.destinationairport
                    }
                    LIMIT
                        10;
                """,
                couchbase.options.QueryOptions(
                    named_parameters={
                        "source_airport": source_airport,
                        "destination_airport": destination_airport
                    }
                ),
            )
            results: list[dict] = list()
            for result in query.rows():
                results.append(result.dict)
            return results


        @agentc.catalog.tool
        def find_two_layover_flights(
            source_airport: str,
            destination_airport: str,
        ) -> list[dict]:
            """Find all two-layover (indirect) flights between two airports."""
            query = cluster.query(
                """
                    FROM
                        `travel-sample`.inventory.route r1,
                        `travel-sample`.inventory.route r2,
                        `travel-sample`.inventory.route r3
                    WHERE
                        r1.sourceairport = $source_airport AND
                        r1.destinationairport = r2.sourceairport AND
                        r2.destinationairport = r3.sourceairport AND
                        r3.destinationairport = $destination_airport
                    SELECT VALUE {
                        "airlines"     : [r1.airline, r2.airline, r3.airline],
                        "layovers"     : [r1.destinationairport],
                        "from_airport" : r1.sourceairport,
                        "to_airport"   : r3.destinationairport
                    }
                    LIMIT
                        10;
                """,
                couchbase.options.QueryOptions(
                    named_parameters={
                        "source_airport": source_airport,
                        "destination_airport": destination_airport
                    }
                ),
            )
            results: list[dict] = list()
            for result in query.rows():
                results.append(result)
            return results

    Python tools are Python functions that are decorated with the :python:`agentc.catalog.tool` decorator.
    By default, the function's name (here, :python:`find_one_layover_flights` and :python:`find_two_layover_flights`)
    and the function's docstring (the triple-quoted string immediately under the function signature) are used to
    populate the decorator's ``name`` and ``description`` fields, though these can also be explicitly specified by using
    :python:`agentc.catalog.tool(name=..., description=...)`.

    The arguments of each function (``source_airport`` and ``destination_airport``) must be appropriately typed for the
    agent to correctly invoke the function.
    Similar to the ``find_direct_routes_between_airports`` tool, both fields are string-valued.

    .. note::

        In general, it is good practice to also attach return types for your functions (here, :python:`-> list[dict]`)
        -- but this is not a strict requirement for our agent to invoke the function.

Using Agent Catalog
^^^^^^^^^^^^^^^^^^^

LLMs, and by extension agents, are very sensitive to their initial conditions (e.g., the prompt text, a tool's name,
etc...).
For agent developers like us, using a tried-and-true versioning system like Git is essential to adequately capturing
these initial conditions for reproducibility down-the-line.
If you have set the correct environment variables (or populated ``.env`` appropriately), all we need to do now is
``git add`` the prompts and tools we just authored and commit them with ``git commit``.
Behind the scenes, ``agentc index`` and ``agentc publish`` will run to index these tools and prompts to a
local catalog file and to your Couchbase instance.

Assuming that you have placed your tools in a ``tools`` folder and your prompts in a ``prompts`` folder
(corresponding to the ``add-hook-for`` option from ``agentc init``), run the commands below to commit your files to
Git and to index + publish your artifacts.

.. code-block:: ansi-shell-session

    $ git add * ; git add .gitignore .env.example .pre-commit-config.yaml
    $ git commit -m "Initial commit"

Finally, to use our tools and prompts in an application, we'll just need to create an :python:`agentc.Catalog` instance
and call the ``find`` method.

.. code-block:: python

    import agentc
    import dotenv

    dotenv.load_dotenv()

    # AGENT_CATALOG_CONN_STRING, AGENT_CATALOG_USERNAME, and AGENT_CATALOG_PASSWORD
    # must be set as environment variables or passed as parameters here.
    catalog = agentc.Catalog()

    # Grab a tool by name.
    tool = catalog.find("tool", name="find_direct_routes_between_airports")
    print(tool.func(source_airport="SFO", destination_airport="LAX"))

    # Grab a prompt by name.
    prompt = catalog.find("prompt", name="route_finding_node")
    print(prompt.content)

    # Use the tool specified in the prompt.
    tool_from_prompt = prompt.tools[0].func
    print(tool_from_prompt(
        source_airport="SFO",
        destination_airport="LAX",
    ))

In addition to tracking the initial conditions of our agents, we are also interested in intuiting the exact
circumstances that led to an agent's output.
To support observability with Git-backed reproducibility, Agent Catalog supports "Span"-based logging.
For developers using LangGraph or LlamaIndex, Agent Catalog Spans work behind the scenes to log all agent activity to a
local file and to Couchbase.
For users interested in using Spans directly, ``Span`` objects are created from ``Catalog`` instances:

.. code-block:: python

    catalog = agentc.Catalog()
    my_span = catalog.Span(name="my_span")

    # See the docs for examples on how to use me!
    my_span.log(content={"kind": "user", "value": "Hello world!"})

Step #2: Building Agents with LangGraph
---------------------------------------

At this point, we have not touched LangGraph -- and that's important to note!
There are many agent frameworks available for you to use, but most (if not all) require tools and prompts.
Agent Catalog is intended to be **framework-agnostic**.
To handle the orchestration of our agents for this example, we will use LangGraph.

The LangGraph core does not have a notion of "agents".
LangGraph instead uses *nodes* and *edges*.
Loosely inspired by the Pregel model, all nodes within the same graph accept "state" and return "state" for other nodes
to use.
In most cases, state will minimally consist of the graph's history (e.g., what the user asked, what an agent responded
with, etc...).
For our agent, we add three extra fields to our state (extending the helper ``agentc_langgraph.agent.State`` class):

.. code-block:: python

    # From the agentc_langgraph.agent.State class:
    # messages: list[langchain_core.messages.BaseMessage]
    # is_last_step: bool
    # previous_node: typing.Optional[list[str]]
    class State(agentc_langgraph.agent.State):
        needs_clarification: bool
        endpoints: typing.Optional[dict]
        routes: typing.Optional[list[dict]]

We will describe how this state is used in the implementation of our agents (realized using LangGraph nodes) below.
Each agent below sub-classes a helper "ReAct" agent that removes some boilerplate for Agent Catalog to interface
with LangGraph's built-in ReAct agent.

.. dropdown:: Front Desk Agent (Node)

    .. code-block:: python

        def talk_to_user(
            span: agentc.Span,
            message: str,
            requires_response: bool = True,
        ):
            # We use "Assistant" to differentiate between the
            # "internal" AI messages and what the user sees.
            span.log(agentc.span.AssistantContent(value=message))
            if requires_response:
                print("> Assistant: " + message)
                response = input("> User: ")
                span.log(agentc.span.UserContent(value=response))
                return response
            else:
                print("> Assistant: " + message)

        class FrontDeskAgent(agentc_langgraph.agent.ReActAgent):
            def __init__(
                self,
                catalog: agentc.Catalog,
                span: agentc.Span,
            ):
                chat_model = langchain_openai.chat_models.ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                )
                super().__init__(
                    chat_model=chat_model,
                    catalog=catalog,
                    span=span,
                    prompt_name="front_desk_node",
                )
                self.introductory_message: str = \
                    "Please provide the source and destination airports."

            def _invoke(
                self,
                span: agentc.Span,
                state: State,
                config: langchain_core.runnables.RunnableConfig,
            ) -> State:
                if len(state["messages"]) == 0:
                    # This is the first message in the conversation.
                    response = talk_to_user(span, self.introductory_message)
                    state["messages"].append(langchain_core.messages.HumanMessage(content=response))
                else:
                    # Display the last message in our conversation to our user.
                    response = talk_to_user(span, state["messages"][-1].content)
                    state["messages"].append(langchain_core.messages.HumanMessage(content=response))

                # Give the working state to our agent.
                agent = self.create_react_agent(span)
                response = agent.invoke(input=state, config=config)

                # 'is_last_step' and 'response' comes from the prompt's output format.
                # Note this is a direct mutation on the "state" given to the Span!
                structured_response = response["structured_response"]
                state["messages"].append(
                    langchain_core.messages.AIMessage(structured_response["response"])
                )
                state["is_last_step"] = structured_response["is_last_step"]
                state["needs_clarification"] = structured_response["needs_clarification"]
                if state["is_last_step"]:
                    talk_to_user(span, structured_response["response"], requires_response=False)
                return state

    Outside of our agent we define a :python:`talk_to_user` tool, which interfaces with the user through the console
    and records user + assistant activity to an Agent Catalog :python:`Span` instance.

    Starting with our constructor, the prompt we specified earlier is retrieved by name with
    :python:`prompt_name="front_desk_node"`.
    For this example, we are using ``gpt-4o-mini`` but any LangChain-compatible chat model can be used here.

    .. note::

        Note that we pass an OpenAI chat model instance (specifically, ``gpt-4o-mini`` with :python:`temperature=0`)
        to the parent class.
        This is one of many initial conditions that would not be captured if we versioned only our prompts!

    Child classes of :python:`agentc_langgraph.agent.ReActAgent` must also implement the :python:`_invoke` method, which
    handles the invocation of our LLM and how to mutate the input :python:`State` instance for use by other agents.
    Our front desk agent always starts with a pre-canned message when first interacting with a user, but will invoke
    a ReAct agent containing our message history for all subsequent responses.
    After the agent invocation, we mutate the :python:`state` object to:

    1. Add the LLM's output to our conversational history list, :python:`"messages"`;
    2. Set the :python:`is_last_step` and :python:`needs_clarification` flags from the LLM's structured response
       (according to the output type defined in the prompt); and
    3. Responds to the user if :python:`is_last_step` is raised.

    Once our :python:`state` object has been modified, we emit our state for other agents (or more accurately, nodes)
    to use in their :python:`_invoke` method.

.. dropdown:: Endpoint Finding Agent (Node)

    .. code-block:: python

        class EndpointFindingAgent(agentc_langgraph.agent.ReActAgent):
            def __init__(self, catalog: agentc.Catalog, span: agentc.Span):
                chat_model = langchain_openai.chat_models.ChatOpenAI(
                    model="gpt-4o",
                    temperature=0,
                )
                super().__init__(
                    chat_model=chat_model,
                    catalog=catalog,
                    span=span,
                    prompt_name="endpoint_finding_node",
                )

            def _invoke(
                self,
                span: agentc.Span,
                state: State,
                config: langchain_core.runnables.RunnableConfig,
            ) -> State:
                # Give the working state to our agent.
                agent = self.create_react_agent(span)
                response = agent.invoke(input=state, config=config)

                # 'source' and 'dest' comes from the prompt's output format.
                # Note this is a direct mutation on the "state" given to the Span!
                structured_response = response["structured_response"]
                state["endpoints"] = {
                    "source": structured_response["source"],
                    "destination": structured_response["dest"]
                }
                state["messages"].append(response["messages"][-1])
                return state

    The endpoint finding agent is much simpler than our front desk agent (with respect to implementation).
    Again, using the output type defined in our prompt, we set the source and destination of our state to be the
    :python:`"source"` and :python:`"dest"` fields of the LLM's structured response.


.. dropdown:: Route Finding Agent (Node)

    .. code-block:: python

        class RouteFindingAgent(agentc_langgraph.agent.ReActAgent):
            def __init__(
                self,
                catalog: agentc.Catalog,
                span: agentc.Span,
            ):
                chat_model = langchain_openai.chat_models.ChatOpenAI(
                    model="gpt-4o",
                    temperature=0
                )
                super().__init__(
                    chat_model=chat_model,
                    catalog=catalog,
                    span=span,
                    prompt_name="route_finding_node",
                )

            def _invoke(
                self,
                span: agentc.Span,
                state: State,
                config: langchain_core.runnables.RunnableConfig,
            ) -> State:
                # Give the working state to our agent.
                agent = self.create_react_agent(span)
                response = agent.invoke(input=state, config=config)

                # We will only attach the last message to our state.
                # Note this is a direct mutation on the "state" given to the Span!
                structured_response = response["structured_response"]
                state["messages"].append(response["messages"][-1])
                state["routes"] = structured_response["routes"]
                state["is_last_step"] = structured_response["is_last_step"] is True
                return state

    The route finding agent is also relatively simple (compared to our front desk agent).
    Using the output type defined in our prompt, we set the routes and the :python:`"is_last_step"` flag of our state
    using the LLM's structured response.

Having defined all of our nodes, let us now define our graph.

.. dropdown:: Travel Application Graph

    .. code-block:: python

        catalog = agentc.Catalog()
        span = catalog.Span(name="root_span")
        workflow = langgraph.graph.StateGraph(State)

    To start, we create a :python:`langgraph.graph.StateGraph` instance that accepts the :python:`State` *class* above.

    .. code-block:: python

        front_desk_agent = FrontDeskAgent(catalog, span)
        endpoint_finding_agent = EndpointFindingAgent(catalog, span)
        route_finding_agent = RouteFindingAgent(catalog, span)
        workflow.add_node("front_desk_agent", front_desk_agent)
        workflow.add_node("endpoint_finding_agent", endpoint_finding_agent)
        workflow.add_node("route_finding_agent", route_finding_agent)
        workflow.set_entry_point("front_desk_agent")

    Next we add our nodes to our graph.
    The first argument of the :python:`add_node` method is a node ID (in this case, the name of the variable bound to
    each agent).
    The second argument of the :python:`add_node` method is the agent itself (more generally, any callable object).
    The last line with :python:`set_entry_point` marks our front desk agent as the first node to run when the graph is
    invoked.

    .. code-block:: python

        def out_front_desk_edge(
            state: State,
        ) -> typing.Literal["endpoint_finding_agent", "front_desk_agent", "__end__"]:
            if state["is_last_step"]:
                return langgraph.graph.END
            elif state["needs_clarification"]:
                return "front_desk_agent"
            else:
                return "endpoint_finding_agent"


        def out_route_finding_edge(
            state: State,
        ) -> typing.Literal["front_desk_agent", "endpoint_finding_agent"]:
            if state["routes"] or state["is_last_step"]:
                return "front_desk_agent"
            else:
                return "endpoint_finding_agent"

        workflow.add_conditional_edges(
            "front_desk_agent",
            out_front_desk_edge,
        )
        workflow.add_edge("endpoint_finding_agent", "route_finding_agent")
        workflow.add_conditional_edges(
            "route_finding_agent",
            out_route_finding_edge,
        )

    Last but not least, we need to connect our nodes together using edges.
    Outgoing edges in LangGraph are functions that accept an input :python:`state` (of the same type used by our nodes)
    and return the name of node that this :python:`state` should be forwarded to.
    The front desk agent has three outgoing edges:

    1. to the terminal :python:`__end__` node if :python:`"is_last_step"` is raised, which stops the graph computation;
    2. back to itself if :python:`"needs_clarification"` is raised; and
    3. to the endpoint finding agent for all other instances of :python:`state`.

    The endpoint finding agent unconditionally moves to the route finding agent (thus the use of :python:`add_edge`
    instead of :python:`add_condition_edges`).
    The route finding agent has two outgoing edges:

    1. to the front desk agent if :python:`routes` is set or if our route finding agent has raised the
       :python:`is_last_step` flag itself; and
    2. back to the endpoint finding agent for all other instances of :python:`state`.

    Finally, to see our graph in action, we compile and call the :python:`invoke` method of our graph:

    .. code-block:: python

        graph = workflow.compile()
        span.state = {
            "messages": [],
            "endpoints": None,
            "routes": None,
            "needs_clarification": False,
            "is_last_step": False,
        }
        with span:
            graph.invoke(input=span.state)

Step #3: Iteratively Improving our Agent
----------------------------------------

In this section, we will illustrate how you can "tune" your agent system in an ad-hoc (but provenance-capturing) manner.

To start, let's find a route from SFO to LAX.

.. code-block:: text

  > Assistant: Please provide the source and destination airports.

  > User: I want to go to LA. I am in the north bay area.

  > Assistant: Here are the direct flight options from the North Bay Area to Los Angeles:
    **From Charles M. Schulz–Sonoma County Airport (STS) to Los Angeles International Airport (LAX):**
    - Alaska Airlines (AS)
    - American Airlines (AA)

    **From San Francisco International Airport (SFO) to Los Angeles International Airport (LAX):**
    - Alaska Airlines (AS)
    - Delta Airlines (DL)
    - United Airlines (UA)
    - US Airways (US)
    - Virgin America (VX)
    - Southwest Airlines (WN)
    - American Airlines (AA)

    **From Oakland International Airport (OAK) to Los Angeles International Airport (LAX):**
    - Delta Airlines (DL)
    - AirTran Airways (FL)
    - Southwest Airlines (WN)

    You have several options to choose from, depending on your preferred airport and airline. Let me know if you
    need further assistance with booking or additional information!

  > User: That's all, thanks

  > Assistant: You're welcome! If you have any more questions in the future, feel free to ask. Have a great trip
    to LA!

Next, let's try a set of endpoints that requires one layover.
Specifically, we want a route from Canyonlands Field Airport (IATA ``'CNY'``) to LAX.

.. code-block:: text

  > Assistant: Please provide the source and destination airports.

  > User: i want to go to LAX from Canyonlands Field Airport

  > Assistant: To travel from Canyonlands Field Airport (CNY) to Los Angeles International Airport (LAX), you will
    likely need to book a connecting flight, as there may not be direct flights available. You can check with
    airlines that operate from CNY for available routes and connections. Additionally, consider checking travel
    websites or consulting with a travel agent to find the best options for your trip.

This is **not** a correct response.
To intuit why our application has failed, we will use the logs generated by our application.
Specifically, we will look at our logs using Agent Catalog's built-in Query Service UDFs:

.. code-block:: sql

    SELECT
        *
    FROM
        `travel-sample`.agent_activity.Sessions() s
    WHERE
        s.sid = `travel-sample`.agent_activity.LastSession();

The results from the query above show that the "Front Desk" agent has incorrectly assumed that the user input is not
relevant to route planning.

1. To fix this, let us modify our prompt.
   Open the file ``prompts/front_desk.yaml`` and uncomment all parts of the ``content --> agent_instructions`` list.

   .. code-block:: yaml

     - >
       Your task is to respond to the user AND decide if the conversation should
       end based on the user's response.
       If you have any routes that have been given to by another agent, respond
       to the user in Markdown illustrating the routes.

     - >
       If the user asks for help with flight planning but there are no source and
       destination cities provided, set the 'needs_clarification' field to True
       and provide a polite response.

     - >
       If the user asks / replies with anything not related to flight planning, set
       the 'is_last_step' field to True and 'needs_clarification' to True.
       DO NOT continue the conversation if the user's input / response is not related
       to flight planning.
       For example, the following responses should end the conversation (set
       'is_last_step' to True):
       - I need help with my hotel reservation. ==> is_last_step: True
       - Can you help me with my car rental? ==> is_last_step: True
       - I need recommendations for restaurants in the area. ==> is_last_step: True

     - >
       If the user wants to end the conversation, set the 'is_last_step' field to True
       and provide a polite response.
       For example:
       - Thanks! That's all I need. ==> is_last_step: True
       - I'm done for now. ==> is_last_step: True
       - That's all for today. ==> is_last_step: True

2. Next, we will create a new commit that captures this change.

   .. code-block:: ansi-shell-session

     $ git add prompts/front_desk.yaml
     $ git commit -m "Fixing front desk agent."

3. Now, let us try the same input again with our agent system.

   .. code-block:: text

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

     > Assistant: You're welcome! If you have any more questions in the future, feel free to reach out.
       Safe travels!

   ...and it seems our fix has worked!

To conclude this section, users of Agent Catalog are expected (and encouraged) to make small changes like this
frequently and ad-hoc (like we did here).
When we move past this ad-hoc testing to more qualitative and structured evaluation, the role Agent Catalog plays is
further magnified (see the example source `here <https://github.com/couchbaselabs/agent-catalog/tree/master/examples/with_langgraph/evals>`__
for how built in testing frameworks like :python:`pytest` are used to facilitate an evaluation environment).
Git-backed versioning allows agent developers to seamlessly switch between agent versions using Git commands (see `here <faqs.html#git-versioning-questions>`__
for guidance on using Git for this).
