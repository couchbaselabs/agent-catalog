.. role:: python(code)
   :language: python

Agent Catalog Record Entries
============================

As of date, Agent Catalog supports five different types of records (four types of tools and the generic prompt).

Tool Catalog Records
--------------------

Tools are explicit actions that an agent can take to accomplish a task.
Agent Catalog currently supports four types of tools: Python function tools, SQL++ query tools, semantic search tools,
and HTTP request tools.

Python Function Tools
^^^^^^^^^^^^^^^^^^^^^

The most generic tool is the Python function tool, which is associated with a function in `.py` file.
To signal to Agent Catalog that you want to mark a function as a tool, you must use the `@tool` decorator.

.. literalinclude:: ../../templates/tools/python_function.py

SQL++ Query Tools
^^^^^^^^^^^^^^^^^

SQL++ is the query language used by Couchbase to interact with the data stored in the cluster.
To create a SQL++ query tool, you must author a ``.sqlpp`` file with a header that details various metadata.
If you are importing an existing SQL++ query, simply prepend the header to the query.

.. literalinclude:: ../../templates/tools/sqlpp_query.sqlpp

Semantic Search Tools
^^^^^^^^^^^^^^^^^^^^^

Semantic search tools are used to search for text that is *semantically similar* to some query text.
To create a semantic search tool, you must author a ``.yaml`` file with the ``record_kind`` field populated with
``semantic_search``.

.. literalinclude:: ../../templates/tools/semantic_search.yaml

HTTP Request Tools
^^^^^^^^^^^^^^^^^^

HTTP request tools are used to interact with external services via REST API calls.
The details on how to interface with these external services are detailed in a standard OpenAPI spec (see
`here <https://swagger.io/specification/>`__ for more details).
To create an HTTP request tool, you must author a ``.yaml`` file with the ``record_kind`` field populated with
``http_request``.
One tool is generated per specified endpoint.

.. literalinclude:: ../../templates/tools/http_request.yaml

To know more on generating your OpenAPI spec, check out the schema `here <https://spec.openapis.org/oas/v3.1.0.html#schema>`__.
For an example OpenAPI spec used in the ``travel-sample`` agent, see `here <https://github.com/couchbaselabs/agent-catalog/blob/master/libs/agentc_testing/agentc_testing/resources/travel_agent/rewards_spec.json>`__.

Prompt Records
--------------

Prompts in Agent Catalog refer to the aggregation of all **all** inputs (tool choices, unstructured prompts, output
types, etc...) given to an LLM (or an agent framework).

.. literalinclude:: ../../templates/prompts/prompt.yaml

.. tip::

    The ``content`` field of Agent Catalog prompt entries can be either be completely unstructured (e.g., persisted
    as a single string) or as a YAML object (of arbitrary nesting) structuring specific parts of your prompt.
    For example, suppose we are given the prompt record below:

    .. code-block:: yaml

        name: my_prompt

        description: A prompt for validating the output of another agent.

        content:
            agent_instructions: |
                Your task is to validate the line of thinking using
                the previous messages.
            format_instructions: |
                You MUST return your answer in all caps.

    Upon fetching this prompt from the catalog, we can access the ``content`` field as a dictionary.
    This is useful for agent frameworks that require specific small snippets of text (e.g., "instructions",
    "objective", etc...)

    .. code-block:: python

        import agentc
        import your_favorite_agent_framework

        catalog = agentc.Catalog()
        my_prompt = catalog.find("prompt", name="my_prompt")
        my_agent = your_favorite_agent_framework.Agent(
            instructions=my_prompt.content["agent_instructions"],
            output={
                "type": [True, False],
                "instructions": my_prompt.content["format_instructions"]
            }
        )

