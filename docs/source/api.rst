.. role:: python(code)
   :language: python

Package Documentation
=====================

`agentc` Package
----------------

.. autopydantic_settings:: agentc.catalog.Catalog
    :settings-show-config-summary: False
    :settings-show-json: False
    :settings-show-validator-members: False
    :settings-show-validator-summary: False

.. autopydantic_model:: agentc.span.Span
    :model-show-config-summary: False
    :model-show-json: False
    :model-show-validator-members: False
    :model-show-validator-summary: False
    :members: new, log, identifier, enter, exit, logs
    :exclude-members: logger, model_post_init


Integration Packages
--------------------

LangChain
^^^^^^^^^

.. autoclass:: agentc_langchain.chat.Callback
    :exclude-members: on_chat_model_start, on_llm_end, model_post_init

.. automodule:: agentc_langchain.cache
    :members: cache, initialize
    :exclude-members: CacheOptions

.. autopydantic_settings:: agentc_langchain.cache.CacheOptions
    :settings-show-validator-summary: False
    :settings-show-validator-members: False
    :settings-show-json: False
    :exclude-members: Cluster

LangGraph
^^^^^^^^^

.. automodule:: agentc_langgraph.tool
    :members:

.. automodule:: agentc_langgraph.agent
    :members:
    :exclude-members: create_react_agent

.. automodule:: agentc_langgraph.graph
    :members:
    :exclude-members: name, ainvoke, astream, invoke, stream, get_graph

.. automodule:: agentc_langgraph.state
    :members:
    :exclude-members: AsyncCheckpointSaver, CheckpointOptions, get, get_tuple, list, put, put_writes

..
    TODO (GLENN): Add AsyncCheckpointSaver to the docs when the bug is resolved.

.. autopydantic_settings:: agentc_langgraph.state.CheckpointOptions
    :settings-show-validator-summary: False
    :settings-show-validator-members: False
    :settings-show-json: False
    :exclude-members: Cluster, AsyncCluster

LlamaIndex
^^^^^^^^^^

.. automodule:: agentc_llamaindex.chat
    :members:
    :exclude-members: on_event_start, on_event_end, start_trace, end_trace
