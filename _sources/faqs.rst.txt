.. role:: python(code)
   :language: python

Frequently Asked Questions
==========================

Welcome to the FAQ section of the project documentation!
This section provides answers to common questions about the Agent Catalog project (key concepts, solutions to
common issues, guidance on using various features, etc...).
For additional information, consult the documentation or community resources.

Which Couchbase Capella or Server version should I use?
-------------------------------------------------------
Agent Catalog uses Vector search at its base, so any Couchbase version above and inclusive of ``7.6`` should be used. If you are a new user, we recommend using the latest version!

Is there a dependency on Agent Development frameworks?
------------------------------------------------------
No, ``agentc`` does not depend on any Agent Development frameworks and is compatible with most of the popular frameworks in the market such as Controlflow, Langchain, etc.
However, the `agent-catalog-example <https://github.com/couchbaselabs/agent-catalog-example>`_ repository uses Controlflow at its base to show a sample application using ``agentc``.


What does Agent Catalog add to my Couchbase bucket?
---------------------------------------------------

When you persist catalogs using the ``agentc publish`` `command <cli.html#agentc-publish>`_, Agent Catalog creates a scope called ``agent_catalog`` within a user-specified bucket. Inside this scope, two collections are created:

1. ``<kind>_catalog``: Stores individual catalog items. Following is an example tool present in this collection from the ``travel-sample`` example application:

.. code-block:: json
       :caption: tool_catalog collection - description of one tool from catalog

       {
         "record_kind": "semantic_search",
         "name": "get_travel_blog_snippets_from_user_interests",
         "description": "Fetch snippets of travel blogs using a user's interests.\n",
         "source": "src/resources/agent_c/tools/blogs_from_interests.yaml",
         "version": {
           "timestamp": "2024-10-23 07:16:18.517967+00:00",
           "identifier": "c33204b0bb39c954e10dbcc1e930cee814361945",
           "is_dirty": false,
           "version_system": "git",
           "metadata": null
         },
         "embedding": [-0.027521444484591484, "..."],
         "annotations": {
           "ccpa_2019_compliant": "true",
           "gdpr_2016_compliant": "true"
         },
         "input": "{\n  \"type\": \"object\",\n  \"properties\": {\n    \"user_interests\": {\n      \"type\": \"array\",\n      \"items\": { \"type\": \"string\" }\n    }\n  }\n}\n",
         "vector_search": {
           "bucket": "travel-sample",
           "scope": "inventory",
           "collection": "article",
           "index": "articles-index",
           "vector_field": "vec",
           "text_field": "text",
           "embedding_model": "sentence-transformers/all-MiniLM-L12-v2",
           "num_candidates": 3
         },
         "secrets": [{
           "couchbase": {
             "conn_string": "CB_CONN_STRING",
             "username": "CB_USERNAME",
             "password": "CB_PASSWORD"
           }
         }],
         "identifier": "src/resources/agent_c/tools/blogs_from_interests.yaml:get_travel_blog_snippets_from_user_interests:git_c33204b0bb39c954e10dbcc1e930cee814561945",
         "catalog_identifier": "53010a92d74f96851fb36fc2c69b9c3337140890"
       }

2. ``<kind>_metadata``: Contains metadata for each version of the catalog. Following is an example tool catalog metadata present in this collection from the ``travel-sample`` example application:

.. code-block:: json
       :caption: tool_metadata collection - metadata associated with a catalog version

       {
         "schema_version": "0.0.0",
         "library_version": "v0.0.0-0-g0",
         "kind": "tool",
         "embedding_model": "sentence-transformers/all-MiniLM-L12-v2",
         "version": {
           "timestamp": "2024-10-23 07:16:15.058405+00:00",
           "identifier": "53010a92d74f96851fb36fc2c69b9c3337140890",
           "is_dirty": false,
           "version_system": "git",
           "metadata": null
         },
         "source_dirs": [
           "src/resources/agent_c/tools"
         ],
         "project": "main",
         "snapshot_annotations": {}
       }

These two collections are used to search for the particular catalog item later during the find command or provider use. Additionally, these can be used to run queries to analyse trends, etc.

Agent Catalog also creates GSI indexes on these collections for query optimisation as well as a vector index on the ``<kind>_catalog`` collection to perform vector search queries during find.


What does the catalog by the index command contain?
---------------------------------------------------

Use the ``agentc index`` command after defining your tools and prompts to generate a unified catalog. This catalog consolidates both catalog-level and item-specific metadata, making it easy to view all your tools and prompts in one place. It also optimizes storage for efficient vector searches based on item descriptions, enabling you to build upon existing tools and prompts with ease.

The catalog schema (``v1``) includes the following fields, with item schema being specific for a ``semantic_search`` record kind tool:

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

1. ``embedding_model``: Specifies the name of the embedding model used to generate embeddings for catalog items during ``agentc index``.

2. ``kind``: Type of catalog, e.g., `tool`.

3. ``library_version``: Version of ``agentc`` library.

4. ``schema_version``: Version of the catalog schema.

5. ``source_dirs``: List of directories where source files for the catalog items are located.

6. ``version``: Version details for the catalog itself.

   - ``identifier``: Git commit hash for the catalog version.
   - ``is_dirty``: Boolean indicating if there are uncommitted changes.
   - ``timestamp``: Timestamp at the creation of the catalog.

7. ``items``: A list of catalog items with the following fields ( ``record_kind`` = ``semantic_search`` ):

   - ``annotations``: Key-value pairs to annotate each catalog item with specific information.

   - ``description``: A brief description of the tool or prompt, detailing its purpose or functionality.

   - ``embedding``: Embeddings generated for the item description (of dimensions depending on the specified model).

   - ``identifier``: A unique identifier for the item, of the format ``source_of_item:file_name_of_item:git_commit_hash``.

   - ``input``: JSON schema defining the expected input structure for the item.

   - ``name``: Name of the item, matching the function or tool/prompt name.

   - ``record_kind``: Indicates the type of record, eg. ``semantic_search`` for tool kind, that describes the item's purpose.

   - ``secrets``: Secret configurations required for the tool depending on the record kind (for ``semantic_search``, this represents the secrets for Couchbase server used for vector search).

     - ``couchbase``: Connection details for Couchbase, including:

       - ``conn_string``: Connection string to Couchbase server.
       - ``password``: Couchbase account password.
       - ``username``: Couchbase account username.

   - ``source``: The source file location of the item.

   - ``vector_search``: Configuration for vector search on Couchbase.

     - ``bucket``: Name of the Couchbase bucket used.
     - ``collection``: Collection name where items are stored.
     - ``embedding_model``: Embedding model used for vector search.
     - ``index``: Name of the Couchbase index.
     - ``scope``: Scope within the Couchbase bucket.
     - ``text_field``: Field where text is stored for search.
     - ``vector_field``: Field where vectors are stored for search.

   - ``version``: Version information for each item.
     - ``identifier``: Unique hash identifying the version.
     - ``timestamp``: Timestamp of when the version was created.


**Similar to the above item schema of ``record_kind`` = ``semantic_search``, there are three more types of record kinds possible for tools which have a slightly different schema.

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
