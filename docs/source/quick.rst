.. role:: python(code)
   :language: python

Ignoring Files While Indexing
-----------------------------

When indexing tools and prompts, you may want to ignore certain files.
By default the :file:`index` command will ignore files/patterns present in :file:`.gitignore` file.

In addition to :file:`.gitignore`, there might be situation where additional files have to be ignored by agentc and not git.
To add such files/patterns :file:`.agentcignore` file can be used similar to :file:`.gitignore`.

For example, if the project structure is as below:

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

Inorder to avoid that, :file:`.agentcignore` file can be added in :file:`src` directory with the following content to avoid indexing the file containing agent code:

.. code-block:: text

    agent.py
