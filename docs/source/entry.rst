.. role:: python(code)
   :language: python

Agent Catalog Record Entries
============================

As of date, Agent Catalog supports six different types of records (four types of tools, two types of prompts).

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
`here <https://swagger.io/specification/>`_ for more details).
To create an HTTP request tool, you must author a ``.yaml`` file with the ``record_kind`` field populated with
``http_request``.
One tool is generated per specified endpoint.

.. literalinclude:: ../../templates/tools/http_request.yaml

To know more on generating your OpenAPI spec, check out the schema `here <https://spec.openapis.org/oas/v3.1.0.html#schema>`_.
For an example OpenAPI spec used in the ``travel-sample`` agent, see `here <https://github.com/couchbaselabs/agent-catalog-example/blob/master/travel_agent/src/endpoints/rewards_spec.json>`_.

Prompt Catalog Records
----------------------

Prompts in Agent Catalog are more than just a hunk of text: they also contain metadata that help developers build
agents faster.
These prompts can be a part of a larger workflow (e.g., as a nested prompt within an agent framework) or as a standalone
set of instructions.
Agent Catalog currently supports two types of prompts: raw prompts and Jinja templated prompts.

Raw Prompts
^^^^^^^^^^^

Raw prompts are static, predefined text-based instructions used to guide your agent's actions.
Raw prompts are written directly as plain text without any dynamic elements.

.. literalinclude:: ../../templates/prompts/raw_prompt.prompt

Jinja Templated Prompts
^^^^^^^^^^^^^^^^^^^^^^^

In contrast to raw prompts, Jinja templated prompts enable users to author dynamic prompts that can be rendered at
runtime.
If you are working without an agent framework, Jinja templated prompts might make more sense for your use case.

.. literalinclude:: ../../templates/prompts/jinja_prompt.jinja
