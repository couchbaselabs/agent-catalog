.. role:: python(code)
   :language: python

Agent Catalog User Guide
========================

Agent Catalog targets three (non-mutually-exclusive) types of users:

**Agent Builders**
    Those responsible for creating prompts and agents.

**Tool Builders**
    Those responsible for creating tools.

**Agent Analysts**
    Those responsible for analyzing agent performance.

In this short guide, we detail the workflow each type of user follows when using Agent Catalog.
We assume that you have already installed the ``agentc`` package.
If you have not, please refer to the :doc:`Installation <install>` page.

Metrics Driven Development
--------------------------

The Agent Catalog package is not just a tool/prompt catalog, it's a foundation for building agents using metrics-driven
development.
Agent builders will follow this workflow:

1. **Sample Downloading**: Download the starter agent from the :file:`templates/starter_agent` directory.

2. **Agent Building**: The sample agent is meant to be a reference for building your own agents.
   You will need to modify the agent to fit your use case.

   - Agent Catalog integrates with agent applications in two main areas:
     i) by providing tools and prompts to the agent *framework* via :python:`agentc.Provider` instances, and ii) by
     providing auditing capabilities to the agent via :python:`agentc.Auditor` instances.
     The sample agent demonstrates how to use both of these classes.

   - Agent Catalog providers will always return plain ol' Python functions.
     SQL++ tools, semantic search tools, and HTTP request tools undergo some code *generation* (in the traditional
     sense, not using LLMs) to yield Python functions that will easily slot into any agent framework.
     Python tools indexed by :command:`agentc` will be returned as-is.

     .. note::

        Users must ensure that these tools already exist in the agent application's Git repository, or that the Python
        source code tied to the tool can be easily imported using Python's :python:`import` statement.

3. **Prompt Building**: Follow the steps outlined in the `Couchbase-Backed Agent Catalogs`_ section to create prompts.

   - In a multi-team setting, you can also use :command:`agentc find prompt` to see if other team members have
     already created prompts that address your use case.

   - To accelerate prompt building, you can specify your tool requirements in the prompt.
     This will allow Agent Catalog to automatically fetch the tools you need when the prompt is executed.

4. **Agent Execution**: Run your agent!
   Depending on how your :python:`agentc.Auditor` instances are configured, you should see logs in the
   :file:`./agent-activity` directory and/or in the ``agent_activity`` scope of your Couchbase instance.

Couchbase-Backed Agent Catalogs
-------------------------------

The catalog (currently) versions two types of items: tools and prompts.
Both tool builders and prompt builders (i.e., agent builders) will follow this workflow:

1. **Template Downloading**: Use the ``agentc add`` `command <cli.html#agentc-add>`_ to automatically download the
   template of your choice.

2. **Tool/Prompt Creation**: Fill out the template with the necessary information.

3. **Versioning**: All tools and all prompts must be versioned.
   Agent Catalog currently integrates with Git (using the working Git SHA) to version each item.
   **You must be in a Git repository to use Agent Catalog.**

4. **Indexing**: Use the command below to index your tools/prompts:

   .. code-block:: bash

    agentc index [DIRECTORY] --prompts/no-prompts --tools/no-tools

   ``[DIRECTORY]`` refers to the directory containing your tools/prompts.
   This command will create a local catalog and your items will be in the newly created :file:`./agent-catalog` folder.

   .. note::

        When using the :command:`agentc index` command for the first time, Agent Catalog will download an
        embedding model from `HuggingFace <https://huggingface.co/models>`_ (by default, the
        ``sentence-transformers/all-MiniLM-L12-v2`` model) onto your machine (by default, in the ``.model-cache``
        folder).
        Subsequent runs will use this downloaded model (and thus, be faster).

5. **Publishing**: By default, the :command:`agentc index` command will allow you index tools / prompts associated with
   a dirty Git repository.

   1. To publish your items to a Couchbase instance, you must first commit your changes (to Git) and run the
      :command:`agentc index` command on a clean Git repository.
      :command:`git status` should reveal no tracked changes.

      .. tip::

        If you've made minor changes to your repository and don't want to use an entirely new commit ID before
        publishing, add your files to Git with :command:`git add $MY_FILES` and amend your changes to the last commit
        with :command:`git commit --amend`!

   2. Next, you must add your Couchbase connection string, username, and password to the environment.
      The most straightforward way to do this is by running the following commands:

      .. code-block:: bash

        export AGENT_CATALOG_CONN_STRING=couchbase://localhost
        export AGENT_CATALOG_USERNAME=Administrator
        export AGENT_CATALOG_PASSWORD=password

   3. Use the command to publish your items to your Couchbase instance.

      .. code-block:: bash

        agentc publish [[tool|prompt]] --bucket [BUCKET_NAME]

      This will create a new scope in the specified bucket called ``agent_catalog``, which will contain all of your
      items.

   4. Note that Agent Catalog isn't meant for the "publish once and forget" case.
      You are encouraged to run the :command:`agentc publish` command as often as you like to keep your items
      up-to-date.

Assessing Agent Quality
-----------------------

The Agent Catalog package also provides a foundation for analyzing agent performance.
Agent analysts will follow this workflow:

1. **Log Access**: Your first step is to get access to the :python:`agentc.Auditor` captured logs.
   For logs sent to Couchbase, you can find them in the :file:`agent_activity.raw_logs` collection of your Couchbase
   instance.
   For logs stored locally, you can find them in the :file:`./agent-activity` directory.
   *We recommend the former, as it allows for easy ad-hoc analysis through Couchbase Query and/or Couchbase Analytics.*

2. **Log Transformations**: For users with Couchbase Analytics enabled, we provide four views (expressed as
   Couchbase Analytics UDFs) to help you get started with conversational-based agents.
   All UDFs below belong to the scope :file:`agent_activity`.

   .. admonition:: Sessions ``(sid, start_t, vid, msgs)``

        The ``Sessions`` view provides one record per session (alt. conversation).
        Each session record contains:

        i) the session ID ``sid``,

        ii) the session start time ``start_t``,

        iii) the catalog version ``vid``, and

        iv) a list of messages ``msgs``.

        The ``msgs`` field details all events that occurred during the session (e.g., the user's messages, the response
        to the user, the internal "thinking" performed by the agent, the agent's transitions between tasks, etc...).
        The latest session can be found by applying the filter:

        .. code-block:: sql

            WHERE sid = [[MY_BUCKET]].agent_activity.LastSession()

   .. admonition:: Exchanges ``(sid, question, answer, walk)``

        The ``Exchanges`` view provides one record per exchange (i.e., the period between a user question and an
        assistant response) in a given session.
        Each exchange record contains:

        i) the session ID ``sid``,

        ii) the user's question ``question``,

        iii) the agent's answer ``answer``, and

        iv) the agent's walk ``walk`` (e.g., the messages sent to the LLMs, the tools executed, etc...).

        This view is commonly used as input into frameworks like Ragas.

   .. admonition:: ToolCalls ``(sid, vid, tool_calls)``

        The ``ToolCalls`` view provides one record per session (alt. conversation).
        Each tool call record contains:

        i) the session ID ``sid``,

        ii) the catalog version ``vid``, and

        iii) a list of tool calls ``tool_calls``.

        The ``tool_calls`` field details all information around an LLM tool call (e.g., the tool name, the tool-call
        arguments, and the tool result).

   .. admonition:: Walks ``(vid, msgs, sid)``

        The ``Walks`` view provides one record per session (alt. conversation).
        This view is essentially the ``Sessions`` view where all ``msgs`` only contain task transitions.


*The next two steps are under active development!*

3. **Log Analysis**: Once you have a grasp how your agent is working, you'll want to move into the realm of
   "quantitative".
   A good starting point is `Ragas <https://docs.ragas.io/en/latest/getstarted/index.html>`_, where you can use the
   Analytics service to serve "datasets" to the Ragas :python:`evaluate` function [1]_.

4. **Log Visualization**: Users are free to define their own views from the steps above and visualize their results
   using dashboards like `Tableau <https://exchange.tableau.com/en-us/products/627>`_ or
   `Grafana <https://developer.couchbase.com/grafana-dashboards>`_ [2]_.

.. [1] Ragas is one of many tools that can be used to analyze agent performance.
       We are actively working on a suite of tools / solutions to help you express assertions (e.g., bounded task
       graph walks) and incorporate various notions of ground truth in your analysis.

.. [2] Stay tuned for more work around log visualization tailored towards agent analysis!

Ignoring Files While Indexing
-----------------------------

When indexing tools and prompts, you may want to ignore certain files.

By default the :file:`index` command will ignore files/patterns present in :file:`.gitignore` file.

In addition to :file:`.gitignore`, there might be situation where additional files have to be ignored by agentc and not git.
To add such files/patterns :file:`.agentcignore` file can be used similar to :file:`.gitignore`.

For example,

If the project structure is as below:

.. code-block:: text

    project/
    ├── docs/
    │   ├── conf.py
    │   ├── index.rst
    │   └── structure.rst
    ├── src/
    │   ├── tool1.py
    │   ├── tool2.sqlpp
    │   └── agent.py
    ├── prompts/
    │   ├── prompt1.prompt
    │   └── prompt2.jinja
    ├── .gitignore
    └── README.md

:file:`src/agent.py` contains the code for agent which uses the tools and prompts present in the project.
:file:`src` directory contains the code for the agent along with the tools.

While indexing using the command :command:`agentc index --tools src`, :file:`src/agent.py` will be indexed along with the tools present in the :file:`src` directory.

Inorder to avoid that :file:`.agentcignore` file can be added in :file:`src` directory with the following content to avoid indexing the file containing agent code:

.. code-block:: text

    agent.py
