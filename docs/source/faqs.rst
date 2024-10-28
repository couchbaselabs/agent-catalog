.. role:: python(code)
   :language: python

Frequently Asked Questions
==========================

Welcome to the FAQ section of the project documentation!
This section provides answers to common questions about the Agent Catalog project (key concepts, solutions to
common issues, guidance on using various features, etc...).
For additional information, consult the documentation or community resources.

How do I roll back to a previous catalog version?
-------------------------------------------------

Agent Catalog was built on the principle of agent *snapshots*.
Consequently, it is possible to roll back to a previous catalog version :math:`v` if you have :math:`v`'s version ID.
Some common use cases for rolling back to a previous catalog version include performing A/B testing on different
versions of your agent or rolling back your agent due to some regression.

Catalog versions are Git commit hashes.
To roll back to a previous catalog version, follow these steps:

1. **List Catalog Versions** : Start by running the :command:`agentc status` command with the ``--status-db`` flag to
   list all the published catalog versions of tools in your bucket (here, we are checking in ``travel-sample``):

   .. code-block:: bash

       # run agentc status --help for all options
       agentc status --kind tool --status-db --bucket travel-sample

   Running the command above will return a list of all the tool catalog snapshots you have published to Couchbase.

   .. code-block:: console
       :emphasize-lines: 5, 16

       -----------------------------------------------------------------
       TOOL
       -----------------------------------------------------------------
       db catalog info:
           catalog id: 53010a92d74e96851fb36fc2c69b9c3337140890
                   path            : travel-sample.agent_catalog.tool
                   schema version  : 0.0.0
                   kind of catalog : tool
                   repo version    :
                           time of publish: 2024-10-23 07:16:15.058405+00:00
                           catalog identifier: 53010a92d74e96851fb36fc2c69b9c3337140890
                   embedding model : sentence-transformers/all-MiniLM-L12-v2
                   source dirs     : ['src/resources/agent_c/tools']
                   number of items : 24

           catalog id: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                   path            : travel-sample.agent_catalog.tool
                   schema version  : 0.0.0
                   kind of catalog : tool
                   repo version    :
                           time of publish: 2024-10-16 05:34:38.523755+00:00
                           catalog identifier: fe25a5755bfa9af68e1f1fae9ac45e9e37b37611
                   embedding model : sentence-transformers/all-MiniLM-L12-v2
                   source dirs     : ['src/resources/tools']
                   number of items : 2

       -----------------------------------------------------------------

2. **Browse Git Commits**: Next, check the ``catalog id`` from the above output for the Git commit hash at which the
   catalogs were published to the database.
   Open your repository commit history on Github or run the :command:`git log` command in your terminal to view the
   commit history for your project.
   Once you have a comprehensive list of commits, you can decide which catalog version to roll back to.

3. **Perform Rollback**: When you decide which catalog version you want to roll back to, you can move forward
   (or rather, "backward") in three ways:

   a. To revert your changes to a specific commit in a non-destructive manner, run :command:`git revert`.

      .. code-block:: bash

          git revert <commit_hash>..HEAD

      This command will rollback your repository to `<commit_hash>` *but* with a new commit hash.
      This is a safe way to rollback to a previous version without losing your current work, as your existing
      Git commit history will be preserved.

   b. To checkout a particular commit (i.e., all changes associated with some commit), run :command:`git checkout`.

       .. code-block:: bash

           git checkout <commit_hash>

       This command will checkout the commit `<commit_hash>` without creating a new commit.

   c. To revert your changes to a specific commit in a **destructive** manner, run :command:`git reset`.

      .. code-block:: bash

          git reset --hard <commit_hash>

      This command will reset your working Git HEAD to the provided commit if you have not published your changes so
      far.
      **This command is destructive, so make sure all your changes have been committed or are stashed beforehand!**

   For further information on Git, please refer to git documentation
   `here <https://training.github.com/downloads/github-git-cheat-sheet>`_ .


What should my .env contain?
----------------------------

To get started with Agent Catalog, you'll need to initialize certain environment variables in a ``.env`` file located at the
root of your project (make sure the file is created where all your ``agentc`` commands will be running). These variables configure key settings, such as API keys, database connections, and other project-specific options, that are essential for running CLI commands and building agent workflows.

Make sure to review the required variables and populate them with appropriate values before starting your project.

.. code-block:: ini
       :caption: Add the following to your ``.env`` file, and replace the default values with your desired settings

       ------------------------------------------ REQUIRED -----------------------------------------
       # Couchbase-specific environment variables.
       CB_CONN_STRING=localhost
       CB_USERNAME=Administrator
       CB_PASSWORD=password

       # The OpenAI API key.
       OPENAI_API_KEY=...

       ------------------------------------------ OPTIONAL ------------------------------------------
       # These are from the starter agent as described in `travel-agent` example

       # Agent Catalog specific environment variables that identify where the catalog is stored.
       AGENT_CATALOG_CONN_STRING=couchbase://localhost
       AGENT_CATALOG_USERNAME=Administrator
       AGENT_CATALOG_PASSWORD=password
       AGENT_CATALOG_BUCKET=travel-sample

       # For example purposes, we want to see what our agent is doing (this is CF-specific).
       CONTROLFLOW_TOOLS_VERBOSE=true
       PREFECT_LOGGING_LEVEL=CRITICAL

       # ControlFlow specific environment variables (which are really just Prefect environment variables).
       PREFECT_API_URL="http://127.0.0.1:4200/api"

       # Default model used when encoding our tool / prompt descriptions.
       DEFAULT_SENTENCE_EMODEL=sentence-transformers/all-MiniLM-L12-v2

       # To stop sentence_transformers from being fussy about multiple imports.
       TOKENIZERS_PARALLELISM=false

The list above details the environment variables required to enable Agent Catalog functionalities.
Some variables are **mandatory** for using both the CLI commands and the SDK:

1. Couchbase specific environment variables

* ``CB_CONN_STRING``: Couchbase connection string, which can be set to localhost or obtained from Capella. For more info on connection strings, refer to the `official documentation <https://docs.couchbase.com/python-sdk/current/howtos/managing-connections.html#connection-strings>`_.

* ``CB_USERNAME``: Username needed to sign in to your Couchbase cluster, either hosted locally (if ``CB_CONN_STRING`` = ``localhost``) or within your Capella organization. When using Capella, this is the username associated with the database access key required for the connection string set up.

* ``CB_PASSWORD``: Password needed to sign in to your Couchbase cluster, either hosted locally (if ``CB_CONN_STRING`` = ``localhost``) or within your Capella organization. When using Capella, this is the password associated with the database access key required for the connection string set up.

2. LLM Connection

* ``OPENAI_API_KEY``: To start using Agent Catalog functionalities, you require an OpenAI API key. Refer to the section on :ref:`OpenAI API Key usage <How does Agent Catalog use my OpenAI API key?>` to know more about how we leverage OpenAI to enhance agent workflow development.

The rest of the variables are optional and contextual to the ``travel-agent`` example as explained in `this repository <https://github.com/couchbaselabs/agent-catalog-example>`_.


What are the different types of tools and prompts I can create?
---------------------------------------------------------------
You can define four types of tools and two types of prompts, each designed for different functionalities:

1. **Tools**

* **Python Functions** (``.py``) - Define Python functions with specific inputs and outputs, following the prescribed function definitions. The functions are tagged with the ``@tool`` decorator for easy identification and use.

* **SQL++ Query** (``.sqlpp``) - Create Couchbase SQL++ queries that run on your cluster, returning results based on a schema you define. This tool is ideal for working with structured data stored in Couchbase.

* **Semantic Search** (``.yaml``) - Perform semantic searches on specific fields within documents using Couchbase Vector Search. This tool allows you to search for documents by meaning rather than exact keyword matches.

* **HTTP Requests** (``.yaml``) - Configure REST API calls to external endpoints of your choice for data retrieval or interaction. These tools are useful for interacting with external services, retrieving or sending data, or triggering workflows that rely on third-party APIs.

2. **Prompts** - TODO

* **Jinja** (``.jinja``) - These prompts utilize the Jinja templating engine to create dynamic and flexible input templates. They allow you to craft prompts with placeholders, which can be filled at runtime based on the specific context of the agent, enabling powerful and reusable prompt generation.

* **Raw prompts** (``.prompt``) - Raw prompts are static, predefined text-based instructions for the language model. They are written directly as plain text without any dynamic elements. These are best suited for straightforward tasks that require a single-shot interaction or fixed wording for the prompt.


Refer to the templates `here <https://github.com/couchbaselabs/agent-catalog/tree/master/resources/templates>`_ for more information on how to write each tool and prompt.

Can I write multiple tools/prompts in one file?
-----------------------------------------------
It is possible to define multiple tools in a single file for certain types of tools, while prompts must be written one per file.

For Python tools (``record_kind`` = ``python_function``), you can include multiple tools in a single ``.py`` file, as each tool is uniquely identified with the ``@tool`` decorator. Additionally, if you are defining HTTP tools (``record_kind`` = ``http_request``) in YAML, you may specify multiple path entries within the same file, provided that they share the same API specification.

Examples illustrating this are shown below:

.. code-block:: python
       :caption: Example of multiple python tools in a single .py file

       from agentc_core.tool import tool

       @tool
       def search_best_flight_deals() -> list[FlightDeal]:
           """Search for the best flight deals."""
           return None


       @tool
       def create_packing_checklist() -> list[PackingChecklistItem]:
           """Create a packing checklist."""
           return None

.. code-block:: yaml
       :caption: Example of multiple http request tools in a single yaml file

       record_kind: http_request

       open_api:
         filename: ../rewards_spec.json
         operations:
           - path: /create                       # ===> considered as one tool
             method: post
           - path: /rewards/{member_id}          # ===> considered as another tool
             method: get


For other types of tools and for all prompts, you must define one tool or prompt per file. If you'd like to auto-download tools or prompts using default configurations, you can refer to the ``agentc add`` command in the documentation `here <cli.html#agentc-add>`_.

Do CLI commands need to be executed in an order?
------------------------------------------------
While you can run any CLI command at any time, certain commands follow a logical order to ensure proper catalog management.

1. **Indexing**: After creating tools or prompts, you first need to generate the catalog with the ``agentc index`` command. This step prepares the catalog for local use.

2. **Finding**: Once the catalog is indexed, you can perform local searches using the ``agentc find`` command or work programmatically through the Provider.

3. **Publishing**: To persist the catalog in your Couchbase cluster, use the ``agentc publish`` command. This allows database-level searches via ``agentc find --search-db``.

.. note::

       Publishing should only be done after indexing the catalog. For any changes made to the local catalog, you must re-index it, commit the changes to Git, and then publish it again to update the database.

4. **Cleaning**: To remove the catalog and clean up the environment, use the ``agentc clean`` command.

Other commands can be executed at any time and provide valuable information about your development environment.


Can I index and publish catalogs programmatically?
--------------------------------------------------
Yes! The ``agentc_cli`` package enables you to import all the CLI commands directly into your project, allowing you to programmatically manage tasks such as indexing and publishing catalogs. You can write custom scripts that use these commands to automate processes, integrate with existing workflows, etc., allowing you to streamline catalog management and optimize your agent workflow development.

How does Agent Catalog use my OpenAI API key?
---------------------------------------------

Agent Catalog does not use your OpenAI API key directly. While developing agent workflows with your preferred frameworks, a large language model (LLM) is essential for tasks such as response generation and decision-making. Agent Catalog simplifies this process by maintaining a comprehensive catalog of tools and prompts that your agents may require. It generates and stores embeddings of tool and prompt descriptions, allowing for efficient semantic searches to retrieve relevant items.

Agent Catalog itself does not rely on an LLM, which means it does not utilize your API key. The LLM is solely needed by your agent development framework, such as ControlFlow, Langgraph, or similar, to perform tasks like generating responses and executing complex reasoning.

Can I use any LLM I wish to?
-------------------

Absolutely! You are free to choose any LLM for your agent workflow development, as long as the framework you select supports it. This flexibility allows you to tailor your agent’s capabilities to your specific needs and preferences.

