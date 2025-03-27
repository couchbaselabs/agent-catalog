.. role:: python(code)
   :language: python

``agentc`` Command Documentation
================================

The :command:`agentc` command line tool acts as an interface for your Agent Catalog instance.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc)

All sub-commands have a verbosity option (:code:`-v, --verbose`, by default verbosity is 0) and an interactive option
(:code:`-i, --interactive / -ni, --no-interactive`, by default interactivity is enabled).

``add`` Command
---------------

The primary purpose of the :code:`add` command is to import templates for declarative Agent Catalog tools (and prompts).

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["add", "--help"])

See  `here <catalog.html>`_ for more information on the types of catalog entries Agent Catalog currently recognizes.

.. note::

    The :code:`add` command **does not** index the generated tool / prompt for you.
    You are responsible for populating the remaining fields from the generated output and running the subsequent
    :code:`agentc index` command.

.. tip::

    For tools authored in Python, we recommend adding the :python:`agentc.catalog.tool` decorator to your function and
    specifying the containing directory on :code:`agentc index` instead of using the :code:`add` command.
    For example, if you have an existing tool named ``positive_sentiment_analysis_tool`` that is properly documented
    (i.e., has a docstring and descriptive names in the function signature), simply add :code:`@agentc.catalog.tool`
    to the top of your function.

    .. code-block:: python

      import agentc

      @agentc.catalog.tool
      def positive_sentiment_analysis_tool(text_to_analyze: str) -> float:
          """ Using the given text, return a number between 0 and 1.
              A value of 0 means the text is not positive.
              A value of 1 means the text is positive.
              A vale of 0.5 means the text is slightly positive. """
          ...


``clean`` Command
-----------------

The purpose of the :code:`clean` command is to "clean" / prune data from your local and / or remote catalog.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["clean", "--help"])

For remote catalogs possessing multiple catalog versions, you can specify a set of catalog IDs (i.e., Git SHAs) via the
:code:`--catalog-id` flag to delete their associated entries from the remote catalog.
For example, running the command below will delete all tool + prompt + metadata entries associated with catalog versions
``GS53S`` and ``14dFDD``:

.. code-block:: ansi-shell-session

  $ agentc clean -cid GS53S -cid 14dFDD

``env`` Command
---------------

The :code:`env` command displays the current configuration of Agent Catalog as a JSON object (see `here <config.html>`__
for all configuration fields).

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["env", "--help"])

``execute`` Command
-------------------

The :code:`execute` command is a helper command that allows users to directly invoke tools indexed by Agent Catalog.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["execute", "--help"])

The arguments for :code:`agentc execute` are identical to that of :code:`agentc find` (with the exception of the
:code:`{tools|prompts}` argument).
:code:`execute` is useful for verifying declarative tools before running them in your application (e.g., validating
the results of your SQL++ query, checking the results of your semantic search, etc...).

``find`` Command
----------------

The primary purpose of the :code:`find` command is to validate the :code:`query` or :code:`name` arguments used by
a call to :code:`agentc.Catalog:find`.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["find", "--help"])

Search By Name
^^^^^^^^^^^^^^

To find a tool or prompt directly by name, use the :code:`--name` option.
For example, to search for the latest version of the tool "find_user_by_id", you would write / author the following:

.. tab-set::

    .. tab-item:: Command Line

        .. code-block:: ansi-shell-session

            $ agentc find tool --name find_user_by_id

    .. tab-item:: Python Program

        .. code-block:: python

            import agentc

            catalog = agentc.Catalog()
            my_tool = catalog.find("tool", name="find_user_by_id")

Search By Query
^^^^^^^^^^^^^^^

On :code:`agentc index`, descriptions of tools and prompts are forwarded through an embedding model to enable semantic
search of tools and prompts at find time.
This is useful for authoring prompts in a tool-agnostic manner (see
`here <concept.html#couchbase-backed-agent-catalogs>`__ for more information).
To find 3 tools semantically related to "finding users", you would write / author the following:

.. tab-set::

    .. tab-item:: Command Line

        .. code-block:: ansi-shell-session

            $ agentc find tool --query "finding users" --limit 3

    .. tab-item:: Python Program

        .. code-block:: python

            import agentc

            catalog = agentc.Catalog()
            my_tools = catalog.find("tool", query="finding users", limit=3)

Filter By Annotations
^^^^^^^^^^^^^^^^^^^^^

Annotations can be added to tools and prompts, which can serve as optional filters for :code:`--query` at find time.
For example, to search for the most related prompt to "frontdesk agent" tailored towards healthcare
(:code:`domain="healthcare"`), you would write / author the following:

.. tab-set::

    .. tab-item:: Command Line

        .. code-block:: ansi-shell-session

            $ # Use single quotes to interpret the annotations string as a literal here!
            $ agentc find prompt --query "frontdesk agent" --annotations 'domain="healthcare"'

    .. tab-item:: Python Program

        .. code-block:: python

            import agentc

            catalog = agentc.Catalog()
            prompt = catalog.find("prompt", query="frontdesk agent", annotations='domain="healthcare"')

.. tip::

    Annotations on the command line must (generally) follow the regex :code:`KEY="VALUE" (AND|OR KEY="VALUE")*`.
    This string must be specified in between single quotes to properly interpret the double quote.

Local Only Search
^^^^^^^^^^^^^^^^^

By default, Agent Catalog will search the local catalog and attempt (in a best-effort fashion) to search your
Couchbase-backed catalog.
To search for local-only entries for a single :code:`find` command, use the :code:`--no-db` flag.
There is no equivalent flag using a :python:`agentc.Catalog:find` call, but you can force local-only searches for a
:python:`agentc.Catalog` instance by explicitly setting the :python:`conn_string` attribute to :python:`None`.
For example, to find the tool named "get_most_popular_categories" from the local catalog, write / author the following:

.. tab-set::

    .. tab-item:: Command Line

        .. code-block:: ansi-shell-session

            $ agentc find tool --name get_most_popular_categories --no-db

    .. tab-item:: Python Program

        .. code-block:: python

            import agentc

            catalog = agentc.Catalog(conn_string=None)
            tool = catalog.find("tool", name="get_most_popular_categories")

``index`` Command
-----------------

The purpose of the :code:`index` command is to build a *local* index of all tools and prompts.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["index", "--help"])

By default, the :code:`index` command will look for both tools and prompts in the given ``SOURCES``.
To avoid searching for tools or prompts specifically, use the ``--no-tools`` and ``--no-prompts`` flags respectively.
In the example below, Agent Catalog will scan the directories :file:`my_tools_1`, :file:`my_tools_2`, and
:file:`my_tools_3` for only tools.

.. code-block:: ansi-shell-session

   $ agentc index --no-prompts my_tools_1 my_tools_2 my_tools_3

``init`` Command
----------------

The purpose of the :code:`init` command is to initialize your Agent Catalog environment (both locally and on Couchbase).

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["init", "--help"])

The :code:`init` command must be run at least once for each Agent Catalog environment.
By default, :code:`init` will run both locally and on Couchbase, initializing your catalog environment and your
activity environment on each.
For instances where :code:`init` has already been run on Couchbase (or vice-versa), use the ``--no-db`` and
``--no-local`` flags respectively.
In the example below, the catalog environment and the activity environment is only locally initialized:

.. code-block:: ansi-shell-session

  $ agentc init --no-db

``ls`` Command
--------------

The purpose of the :code:`ls` command is to list out all items in the latest version of your Agent Catalog instance.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["ls", "--help"])

TODO

``publish`` Command
-------------------

The primary purpose of the :code:`publish` command is to "snapshot" your local catalog instance and persist this
snapshot to Couchbase.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["publish", "--help"])

The :code:`publish` command, similar to all other Couchbase-interfacing commands (e.g., :code:`clean`, :code:`find`,
etc...) reads Couchbase authentication details from your environment.
To override the bucket being published to, users can specify the bucket name directly via the ``--bucket`` option.
In the example below, both tools and prompts are published to a bucket named ``test_bucket``:

.. code-block:: ansi-shell-session

   $ agentc publish --bucket test_bucket

Users can also choose to selectively publish tools, prompts, or logs to Couchbase.
By default, only tools and prompts are published -- logs are expected to be continuously pushed to Couchbase while your
application is running (thus, the ``logs`` choice is primarily for recovery operations).
In the example below, only tools are published:

.. code-block:: ansi-shell-session

   $ agentc publish tools

``status`` Command
------------------

The purpose of the :code:`status` command is to view *aggregate* information about your Agent Catalog instance.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["status", "--help"])

TODO

``version`` Command
-------------------

The purpose of the :code:`version` command is to display the current version of the ``agentc`` package.

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["version", "--help"])

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["version"])