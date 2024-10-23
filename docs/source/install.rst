.. role:: python(code)
   :language: python

Installation
===============

Building From Package
---------------------

.. important::

    This part is in-the-works! For now, please refer to the `Building From Source`_ section.

Building From Source
--------------------

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

5. You should now have the :command:``agentc`` command line tool. Run :command:``agentc --help`` to verify your
   installation (note that your first run will take a couple of seconds, subsequent runs will be faster).

   .. code-block:: console

       Usage: agentc [OPTIONS] COMMAND [ARGS]...

         A command line tool for AGENT_CATALOG.

       Options:
         -c, --catalog DIRECTORY   Directory of local catalog files. The local catalog DIRECTORY should
                                   be checked into git.  [default: .agent-catalog]
         -a, --activity DIRECTORY  Directory of local activity files (runtime data). The local activity
                                   DIRECTORY should NOT be checked into git, as it holds runtime activity
                                   data like logs, etc.  [default: .agent-activity]
         -v, --verbose             Enable verbose output.
         --help                    Show this message and exit.

       Commands:
         clean    Clean up the catalog folder, the activity folder, any generated files, etc.
         env      Show agentc's environment or configuration parameters as a JSON object.
         execute  Execute specific tool to test it.
         find     Find items from the catalog based on a natural language QUERY string.
         index    Walk the source directory trees (SOURCE_DIRS) to index source files into the local
                  catalog.
         publish  Publish the local catalog to Couchbase DB.
         status   Show the status of the local catalog.
         version  Show the current version of agentc.

         See: https://docs.couchbase.com for more information.

   If you see the output above, you are all set! Head on over to our `docs <docs>`_ or our `recipes <recipes>`_ to start
   developing your agent with Agent Catalog.
