


Do I need to use a specific agent framework (e.g., LangChain) with Agent Catalog?
---------------------------------------------------------------------------------
No, Agent Catalog was designed to work *alongside* existing agent frameworks.
Feel free to use your favorite framework (e.g., LangChain, LangGraph, Controlflow, etc...) when building your agent
application!
For our examples (see `here <https://github.com/couchbaselabs/agent-catalog-example>`_), we use Controlflow.


What is Agent Catalog doing when I run ``agentc index``?
--------------------------------------------------------

The ``agentc index`` command is used to assemble a local tool / prompt catalog from the source files in your project.
Depending on the specified options, the command will index tools, prompts, or (by default) both.
The end result are ``<kind>-catalog.json`` files stored in the ``.agent-catalog`` directory.

Below, we give an example of what fields go into the ``<kind>-catalog.json`` file (specifically, a tool catalog
containing a semantic search tool).

.. code-block:: md

  `embedding_model` *(string)*: Embedding model used to generate the embeddings of the item description.
  `kind` *(string)*: Catalog type (e.g., `tool`).
  `library_version` *(string)*: Version of agentc library.
  `schema_version` *(string)*: Version of catalog schema.
  `source_dirs` *(array)*: Source directories for catalog items.
  `version` *(object)*: Catalog version details.
    `identifier` *(string)*: Git commit hash for catalog.
    `is_dirty` *(boolean)*: Indicates uncommitted changes.
    `timestamp` *(string)*: Timestamp of catalog creation.
  `items` *(array)*: List of catalog items.
      `annotations` *(object key-value)*: Annotations of key-value type.
      `description` *(string)*: Description of the item.
      `embedding` *(array)*: Embeddings of item description.
      `identifier` *(string - `source_of_item:file_name_of_item:git_commit_hash`)*: Unique identifier for the item.
      `input` *(string)*: Input schema for the item.
      `name` *(string)*: Name of the item.
      `record_kind` *(string)*: Type of record (e.g., `semantic_search`).
      `secrets` *(array)*: Secrets configuration.
        `couchbase` *(object)*: Couchbase connection details.
          `conn_string` *(string)*: Couchbase server connection string.
          `password` *(string)*: Couchbase server password.
          `username` *(string)*: Couchbase server username.
      `source` *(string)*: Source file location.
      `vector_search` *(object)*: Vector search configuration.
        `bucket` *(string)*: Couchbase bucket name.
        `collection` *(string)*: Couchbase collection name.
        `embedding_model` *(string)*: Embedding model for vector search.
        `index` *(string)*: Index name for Couchbase.
        `scope` *(string)*: Scope in Couchbase bucket.
        `text_field` *(string)*: Field containing text.
        `vector_field` *(string)*: Field containing vectors.
      `version` *(object)*: Version information.
        `identifier` *(string)*: Git commit hash when this item was recorded.
        `timestamp` *(string)*: Timestamp of creation / last update of item.



What environment variables are required to use Agent Catalog?
-------------------------------------------------------------

To get started with Agent Catalog, you'll need to initialize certain environment variables.
These can be in a ``.env`` file located at the root of your project (where all of your :code:`agentc` commands are
run) *or* manually using :code:`export`.

Make sure to review the required variables and populate them with appropriate values before starting your project.

.. code-block:: ini

       ------------------------------------------ REQUIRED -----------------------------------------
       # Agent Catalog specific environment variables that identify where the catalog is stored.
       AGENT_CATALOG_CONN_STRING=couchbase://localhost
       AGENT_CATALOG_USERNAME=Administrator
       AGENT_CATALOG_PASSWORD=password
       AGENT_CATALOG_BUCKET=travel-sample

       # In case of capella instance or if secure connection is required
       # replace couchbase with couchbases in AGENT_CATALOG_CONN_STRING and add the following
       # AGENT_CATALOG_CONN_ROOT_CERTIFICATE=/path/to/cluster/root/certificate/on/local/system

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

With the exception of the :code:`agentc publish` command, all other commands can be executed in any order.

**Indexing**:
   After creating your tools and/or prompts, you first need to generate a local catalog with the
   :code:`agentc index` command.
   This will build a file-based catalog that you can immediately use (without needing to connect to a Couchbase
   instance).

**Publishing**:
   To persist your catalog entries on Couchbase, use the :code:`agentc publish` command.

Publishing can only be done after indexing the catalog.
To publish new changes, you must first commit your changes to Git and then run the :code:`agentc index` command
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
              tools=True,
              prompts=False
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

       agentc index tools --no-prompts

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
