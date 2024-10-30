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

1. **List Catalog Versions** : Start by running the :command:`agentc status` command with the ``-db`` flag to
   list all the published catalog versions of tools in your bucket (here, we are checking in ``travel-sample``):

   .. code-block:: bash

       # run agentc status --help for all options
       agentc status tool -db --bucket travel-sample

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


What environment variables are required to use Agent Catalog?
-------------------------------------------------------------

To get started with Agent Catalog, you'll need to initialize certain environment variables.
These can be in a ``.env`` file located at the root of your project (where all of your :command:`agentc` commands are
run) *or* manually using :command:`export`.

Make sure to review the required variables and populate them with appropriate values before starting your project.

.. code-block:: ini

       ------------------------------------------ REQUIRED -----------------------------------------
       # Agent Catalog specific environment variables that identify where the catalog is stored.
       AGENT_CATALOG_CONN_STRING=localhost
       AGENT_CATALOG_USERNAME=Administrator
       AGENT_CATALOG_PASSWORD=password
       AGENT_CATALOG_BUCKET=travel-sample

       ------------------------------------------ OPTIONAL ------------------------------------------
       # Couchbase specific environment variables (for the travel-agent example tools).
       CB_CONN_STRING=couchbase://localhost
       CB_USERNAME=Administrator
       CB_PASSWORD=password

       # ControlFlow specific environment variables (which are really just Prefect environment variables).
       CONTROLFLOW_TOOLS_VERBOSE=true
       PREFECT_LOGGING_LEVEL=CRITICAL
       PREFECT_API_URL="http://127.0.0.1:4200/api"

       # To stop sentence_transformers from being fussy about multiple imports.
       TOKENIZERS_PARALLELISM=false

       # The holy OpenAI API key. :-)
       OPENAI_API_KEY=...

For more information on Agent Catalog environment variables, refer to the documentation `here <env.html>`_.

What are the different types of tools and prompts I can create?
---------------------------------------------------------------

Agent Catalog currently supports four types of tools (``python_function``, ``sqlpp_query``, ``semantic_search``,
``http_request``) and two types of prompts (``raw_prompt``, ``jinja_prompt``).
For more information on the types of tools and prompts you can create, refer to the documentation `here <entry.html>`_.

Can I write multiple tools/prompts in one file?
-----------------------------------------------

All prompts must be defined in separate files, as each prompt is uniquely identified by its file name.
However multiple tools can exist in a single file *if you are defining Python tools or HTTP request tools*.
Examples of multiple tools existing within a single file are shown below:

.. code-block:: python

       from agentc import tool

       @tool
       def search_best_flight_deals() -> list[FlightDeal]:
           """Search for the best flight deals."""
           return None


       @tool
       def create_packing_checklist() -> list[PackingChecklistItem]:
           """Create a packing checklist."""
           return None

.. code-block:: yaml

       record_kind: http_request

       open_api:
         filename: ../rewards_spec.json
         operations:
           - path: /create                       # ===> one tool
             method: post
           - path: /rewards/{member_id}          # ===> another tool
             method: get


Do CLI commands need to be executed in a certain order?
-------------------------------------------------------

With the exception of the :command:`agentc publish` command, all other commands can be executed in any order.

**Indexing**:
   After creating your tools and/or prompts, you first need to generate a local catalog with the
   :command:`agentc index` command.
   This will build a file-based catalog that you can immediately use (without needing to connect to a Couchbase
   instance).

**Publishing**:
   To persist your catalog entries on Couchbase, use the :command:`agentc publish` command.

Publishing can only be done after indexing the catalog.
To publish new changes, you must first commit your changes to Git and then run the :command:`agentc index` command
again with a clean Git repository.

For the complete set of Agent Catalog CLI commands, refer to the documentation `here <cli.html>`_.

Can I index and publish catalogs programmatically?
--------------------------------------------------
Yes!
The ``agentc.cmd`` module allows developers to author Python scripts with the same functionality as our CLI commands.
Below we give an example of how to index and publish catalogs programmatically:

.. code-block:: python

       from agentc.cmd import index, publish

       # Index the directory named tools.
       index(
              directory="tools",
              kind="tool",
       )

       # Publish our local catalog.
       publish(
              kind=["tool"],
              bucket="travel-sample",
              username="Administrator",
              password="password",
              connection_string="localhost"
       )

The script above is equivalent to running the following CLI commands:

.. code-block:: bash

       agentc index tools --kind tool

       export AGENT_CATALOG_CONN_STRING=localhost
       export AGENT_CATALOG_USERNAME=Administrator
       export AGENT_CATALOG_PASSWORD=password
       agentc publish tool --bucket travel-sample


Does Agent Catalog require an OpenAI API key?
----------------------------------------------

Agent Catalog does not require an OpenAI API key.

Does Agent Catalog work with any LLM?
-------------------------------------

Yes!
Agent Catalog does not restrict you to a specific language model.
You are free to choose any LLM for your agent workflow development (provided your chosen agent framework supports
the LLM you choose).
