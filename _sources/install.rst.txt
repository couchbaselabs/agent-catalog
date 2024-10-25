.. role:: python(code)
   :language: python

Installation
============

Building From Package
---------------------

.. important::

    This part is in-the-works! For now, please refer to the `Building From Source (with Poetry + pip)`_ or
    `Building From Git (with Poetry)`_ sections below.

Building From Git (with Poetry)
-------------------------------

1. Make sure you have Python 3.12 and `Poetry <https://python-poetry.org/docs/#installation>`_ installed!

2. In your ``pyproject.toml`` file, add the following line in the ``[tool.poetry.dependencies]`` section:

   .. code-block:: toml

       agentc = { git = "git@github.com:couchbaselabs/agent-catalog.git", subdirectory = "libs/agentc", extras = ["langchain"] }

3. Now run :command:`poetry update` to automatically download the ``agentc`` package into your Poetry environment.

Building From Source (with Poetry + pip)
----------------------------------------

1. Make sure you have Python 3.12 and `Poetry <https://python-poetry.org/docs/#installation>`_ installed!

2. Clone this repository.
   Make sure you have your SSH key setup!

   .. code-block:: bash

       git clone git@github.com:couchbaselabs/agent-catalog.git

3. Build the ``agentc`` package using Poetry.

   .. code-block:: bash

       cd libs/agentc
       poetry build

4. You should now have a ``dist`` folder inside ``libs/agentc`` populated with a ``.whl`` file, which you can install
   using :command:`pip`.
   Navigate to your project and install this Python wheel using your project's Python environment.

   .. code-block:: bash

       AGENT_CATALOG_WHEEL_FILE=$(ls $(pwd)/dist/agentc-*.whl | tr -d '\n')

       # Make sure you are using your project's Python environment!
       cd $MY_AGENT_PROJECT
       source $MY_PYTHON_ENVIRONMENT

      pip install "$AGENT_CATALOG_WHEEL_FILE"

   To install the LangChain module associated with Agent Catalog, add ``"[langchain]"`` immediately after the wheel file:

   .. code-block:: bash

      pip install "$AGENT_CATALOG_WHEEL_FILE""[langchain]"


Verifying Your Installation
---------------------------
If you've followed the steps above, you should now have the :command:``agentc`` command line tool.
Run :command:``agentc --help`` to verify your installation (note that your first run will take a couple of seconds,
subsequent runs will be faster).

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
      clean    Delete all agent catalog related files / collections.
      env      Return all agentc related environment and configuration parameters as a JSON object.
      execute  Search and execute a specific tool.
      find     Find items from the catalog based on a natural language QUERY string or by name.
      index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local catalog.
      publish  Upload the local catalog to a Couchbase instance.
      status   Show the status of the local catalog.
      version  Show the current version of agentc.

      See: https://docs.couchbase.com for more information.

If you see the output above, you are all set! Head on over to our `docs <docs>`_ or our `recipes <recipes>`_ to start
developing your agent with Agent Catalog.
