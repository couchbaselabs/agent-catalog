.. role:: python(code)
   :language: python

Log Records
===========

As of date, Agent Catalog supports 10 different types of log records (all varied by content).
Agent Catalog maintains a collection of logs as a **series** of events.

Schema of Logs
--------------

.. autopydantic_model:: agentc_core.activity.models.log.Log

Content in Logs
---------------

.. autoenum:: agentc_core.activity.models.content.Kind
    :members:

.. autopydantic_model:: agentc_core.activity.models.content.SystemContent
.. autopydantic_model:: agentc_core.activity.models.content.ToolCallContent
.. autopydantic_model:: agentc_core.activity.models.content.ToolResultContent
.. autopydantic_model:: agentc_core.activity.models.content.ChatCompletionContent
.. autopydantic_model:: agentc_core.activity.models.content.RequestHeaderContent
.. autopydantic_model:: agentc_core.activity.models.content.UserContent
.. autopydantic_model:: agentc_core.activity.models.content.AssistantContent
.. autopydantic_model:: agentc_core.activity.models.content.BeginContent
.. autopydantic_model:: agentc_core.activity.models.content.EndContent
.. autopydantic_model:: agentc_core.activity.models.content.KeyValueContent
