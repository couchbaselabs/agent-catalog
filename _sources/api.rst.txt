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

LangChain / LangGraph
^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: agentc_langchain.chat.Callback
    :exclude-members: on_chat_model_start, on_llm_end, model_post_init

.. automodule:: agentc_langgraph.tools
    :members:

.. automodule:: agentc_langgraph.agent
    :members:

.. automodule:: agentc_langgraph.graph
    :members:
    :exclude-members: name, ainvoke, astream, invoke, stream

.. autopydantic_settings:: agentc_langchain.cache.CacheOptions
    :settings-show-validator-summary: False
    :settings-show-validator-members: False
    :settings-show-json: False
    :exclude-members: Cluster

.. automodule:: agentc_langchain.cache
    :members: cache

LlamaIndex
^^^^^^^^^^

.. automodule:: agentc_llamaindex.chat
    :members:
    :exclude-members: on_event_start, on_event_end, start_trace, end_trace
