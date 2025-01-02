.. role:: python(code)
   :language: python

Installation
============

Building From Package
---------------------

.. important::

    This part is in-the-works!
    For now, please refer to the `Building From Source (with pip)`_ section below.

Building From Source (with pip)
-------------------------------

1. Make sure you have Python 3.12 and `Poetry <https://python-poetry.org/docs/#installation>`_ installed!

2. Clone this repository.
   Make sure you have your SSH key setup!

   .. code-block:: bash

       git clone git@github.com:couchbaselabs/agent-catalog.git

3. You are now ready to install the Agent Catalog package!
   Using your project's Python environment, execute the following command to install a local package with
   :command:`pip`:

   .. code-block:: bash

       cd agent-catalog
       source $MY_PYTHON_ENVIRONMENT

       # Install the agentc package.
       pip install libs/agentc

   If you are interested in building a ``.whl`` file (for later use in ``.whl``-based installs), use :command:`poetry`
   directly:

   .. code-block:: bash

       cd libs/agentc
       poetry build

Building From Source (with Poetry)
----------------------------------

1. Make sure you have Python 3.12 and `Poetry <https://python-poetry.org/docs/#installation>`_ installed!

2. Clone this repository.
   Make sure you have your SSH key setup!

   .. code-block:: bash

       git clone git@github.com:couchbaselabs/agent-catalog.git

3. Within *your own* ``pyproject.toml`` file, add the following dependency to your project:
   The ``path`` should point to the location of the ``agentc`` package (and is relative to the ``pyproject.toml``
   file itself).

   .. code-block:: toml

       [tool.poetry.dependencies]
       agentc = { path = "agent-catalog/libs/agentc", develop = true }

4. Run the command :command:`poetry update` to install the Agent Catalog package.

   .. code-block:: bash

       cd agent-catalog
       poetry update


Verifying Your Installation
---------------------------
If you've followed the steps above, you should now have the :command:`agentc` command line tool.
Run :command:`agentc --help` to verify your installation (note that your first run will take a couple of seconds as
some libraries like numpy need to be built, subsequent runs will be faster).

.. code-block:: console

    Usage: agentc [OPTIONS] COMMAND [ARGS]...

      The Couchbase Agent Catalog command line tool.

    Options:
      -c, --catalog DIRECTORY         Directory of the local catalog files.  [default: .agent-catalog]
      -a, --activity DIRECTORY        Directory of the local activity files (runtime data).  [default: .agent-activity]
      -v, --verbose                   Flag to enable verbose output.  [default: 0; 0<=x<=2]
      -i, --interactive / -ni, --no-interactive
                                      Flag to enable interactive mode.  [default: i]
      --help                          Show this message and exit.

    Commands:
      add      Interactively create a new tool or prompt and save it to the filesystem (output).
      clean    Delete all or specific (catalog and/or activity) agent related files / collections.
      env      Return all agentc related environment and configuration parameters as a JSON object.
      execute  Search and execute a specific tool.
      find     Find items from the catalog based on a natural language QUERY string or by name.
      index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
      publish  Upload the local catalog to a Couchbase instance.
      status   Show the status of the local catalog.
      version  Show the current version of agentc.

      See: https://docs.couchbase.com for more information.

If you see the output above, you are all set!
To build your first agent, head on over to the `user guide <guide.html>`_ page.
