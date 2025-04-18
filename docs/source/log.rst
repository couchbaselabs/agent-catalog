.. role:: python(code)
   :language: python

.. role:: sql(code)
   :language: sql

Log Records
===========

As of date, Agent Catalog supports 11 different types of log records (all varied by content).
Agent Catalog maintains a collection of logs as a **series** of events.

Schema of Logs
--------------

.. autopydantic_model:: agentc_core.activity.models.log.Log
    :model-show-field-summary: False
    :model-show-config-summary: False
    :model-show-validator-summary: False

Content in Logs
---------------

.. autoenum:: agentc_core.activity.models.content.Kind
    :members:

.. autopydantic_model:: agentc_core.activity.models.content.SystemContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.ToolCallContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.ToolResultContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.ChatCompletionContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.RequestHeaderContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.UserContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.AssistantContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.BeginContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.EndContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.EdgeContent
    :inherited-members: BaseModel

.. autopydantic_model:: agentc_core.activity.models.content.KeyValueContent
    :inherited-members: BaseModel
