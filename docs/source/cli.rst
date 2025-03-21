.. role:: python(code)
   :language: python

`agentc` Command Documentation
==================================

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc)

`add` Command
-------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["add", "--help"])

The primary purpose of the :code:`add` command is to import templates for declarative Agent Catalog tools (and prompts).
See  `here <catalog.html>`_ for more information on the types of catalog entries Agent Catalog currently recognizes.

.. note::

    The :code:`add` command **does not** index the generated tool / prompt for you.
    You are responsible for populating the remaining fields from the generated output and running the subsequent
    :code:`agentc index` command.

.. tip::

    For tools authored in Python, we recommend adding the :python:`agentc.catalog.tool` decorator to your function and
    specifying the containing directory on :code:`agentc index`:

    .. code-block:: python

      import agentc

      @agentc.catalog.tool
      def positive_sentiment_analysis_tool(text_to_analyze: str) -> float:
          """ Using the given text, return a number between 0 and 1.
              A value of 0 means the text is not positive.
              A value of 1 means the text is positive.
              A vale of 0.5 means the text is slightly positive. """
          ...


`clean` Command
---------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["clean", "--help"])

The purpose of the :code:`clean` command is to "clean" / prune data from your local and / or remote catalog.
For remote catalogs possessing multiple catalog versions, you can specify a set of catalog IDs (i.e., Git SHAs) via the
:code:`--catalog-id` flag to delete their associated entries from the remote catalog.
For example, running the command below will delete all tool + prompt + metadata entries associated with catalog versions
``GS53S`` and ``14dFDD``:

.. code-block::

  agentc clean -cid GS53S -cid 14dFDD

`env` Command
-------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["env", "--help"])

The :code:`env` command displays the current configuration of Agent Catalog as a JSON object (see `here <config.html>
for all configuration fields).

`execute` Command
-----------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["execute", "--help"])

The :code:`execute` command is a helper command that allows users to directly invoke tools indexed by Agent Catalog.
The arguments for :code:`agentc execute` are identical to that of :code:`agentc find` (with the exception of the
:code:`{tools|prompts}` argument).
:code:`execute` is useful for verifying declarative tools before running them in your application (e.g., validating
the results of your SQL++ query, checking the results of your semantic search, etc...).

`find` Command
--------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["find", "--help"])

The purpose of the :code:`find` command is to validate the :code:`query` and/or :code:`name` arguments used by a call
to :code:`agentc.Catalog:find`.

TODO

`index` Command
---------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["index", "--help"])

TODO

`init` Command
--------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["init", "--help"])

TODO

`ls` Command
------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["ls", "--help"])

TODO

`publish` Command
-----------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["publish", "--help"])

TODO

`status` Command
----------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["status", "--help"])

TODO

`version` Command
-----------------

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["version", "--help"])

The :code:`version` command displays the current version of the ``agentc`` package:

.. click:run::
  from agentc_cli.main import agentc
  invoke(agentc, args=["version"])