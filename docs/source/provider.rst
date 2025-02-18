.. role:: python(code)
   :language: python

Provider Configuration
======================

This section describes how to configure the ``agentc`` Provider's decorator based on the agent framework used. As mentioned in
the :doc:`api section <api>`, the Provider accepts a decorator (function) to apply to each result yielded by ``get_tools_for()``.

Based on the underlying agent framework being used, this function can differ. For example, Langchain agents take tools as
``langchain_core.tools.BaseTool`` instances while LlamaIndex's agents take tools as ``llama_index.core.tools.BaseTool`` instances.

The decorator is a lambda function which allows the Provider to apply the necessary transformations like type conversion
according to framework to the tools before returning them. Following are various ways to configure the Provider's decorator:

Langchain/LangGraph/CrewAI
--------------------------

While using these frameworks, the decorator is a lambda function that takes the Agent Catalog tool and returns an instance of the
``langchain_core.tools.BaseTool`` class which is called by the ReAct agents during runtime.

Following is an example on how the provider can be defined to use with LangGraph and CrewAI agents:

.. code-block:: python

    import agentc
    from langchain_core.tools import tool
    from langchain_openai.chat_models import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatOpenAI(model="gpt-4o", openai_api_key="<<OPENAI_API_KEY>>", temperature=0)

    provider = agentc.Provider(
        decorator=lambda t: tool(t.func)
    )
    tools = provider.get_item(name="<<TOOL>>", item_type="tool")


LangGraph agent:

.. code-block:: python

    # Define ReAct Agent using Langgraph
    research_agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier="<<PROMPT>>",
    )

CrewAI agent:

.. code-block:: python

    from crewai import Agent, Crew, Process

    # Define Agent using CrewAI
    data_exploration_agent = Agent(
        role="Data Exploration Specialist",
        goal="Perform an exploratory data analysis (EDA) on the provided dataset ...",
        tools=tools,
        verbose=True
    )

    # Define the crew with agents and tasks
    data_analysis_crew = Crew(
        agents=[data_exploration_agent,<<OTHER_AGENTS>>],
        tasks=[<<TASKS>>],
        manager_llm=llm,
        process=Process.hierarchical,
        verbose=True
    )

LlamaIndex
----------

For LlamaIndex agents, the decorator is a lambda function that takes the Agent Catalog tool and returns an instance of the
``llama_index.core.tools.BaseTool`` class which is called by the agent during runtime.

.. note::

   Agent Catalog allows you to define your own tools which should be used to write the base logic. For example, to perform vector
   search, the Agent Catalog ``semantic_search`` Tool should be used instead of LlamaIndex's ``QueryEngineTool`` which
   can then be wrapped as a ``llama_index.core.tools.BaseTool`` instance in the decorator.

Following is an example that converts any Agent Catalog tool to a LlamaIndex ``FunctionTool`` instance and passes it to the ReAct agent:

.. code-block:: python

   import agentc
   from llama_index.core.tools.function_tool import FunctionTool
   from llama_index.core.agent.react import ReActAgent
   from llama_index.llms.openai.base import OpenAI

   llm = OpenAI(model="gpt-4o")

   provider = agentc.Provider(
       decorator=lambda t: FunctionTool.from_defaults
                           (fn=t.func,
                           description=t.meta.description,
                           name=t.meta.name)
   )
   tools = provider.get_item(name="<<TOOL>>", item_type="tool"

   agent = ReActAgent.from_tools(tools=tools, llm=llm, verbose=True, context="<<PROMPT>>")

Controlflow
-----------

For Controlflow agents, the decorator is a lambda function that takes the Agent Catalog tool and returns an instance of the
``controlflow.tools.Tool`` class which is called by them during runtime.

Following is an example that converts any Agent Catalog tool to a Controlflow tool/callable and passes it to the agent:

.. code-block:: python

   import agentc
   from controlflow.tools import Tool
   from controlflow.agent import Agent
   from langchain_openai.chat_models import ChatOpenAI

   llm = ChatOpenAI(model="gpt-4o", temperature=0)

   provider = agentc.Provider(
       decorator=lambda t: Tool.from_function(t.func),
   )
   tools = provider.get_item(name="<<TOOL>>", item_type="tool"

   agent = Agent(
       name="Starter Agent",
       model=llm,
       tools=tools
   )

Information on using the Provider with more frameworks will be added soon!