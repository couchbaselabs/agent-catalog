.. role:: python(code)
   :language: python

Installation
============

Building From Package
---------------------

.. important::

    This part is in-the-works!
    For now, please refer to the `Installing from Source (with Makefile)`_ section below.

Installing from Source (with Makefile)
--------------------------------------

1. Make sure you have :code:`python3.12` and `poetry <https://python-poetry.org/docs/#installation>`_ installed!

2. Make sure you have :code:`make` installed!
   For Mac-based installations, see `here <https://formulae.brew.sh/formula/make>`_.
   For Windows-based installations, see `here <https://gnuwin32.sourceforge.net/packages/make.htm>`_.
   For Ubuntu-based installations, see `here <https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/>`_.

3. Clone this repository.

   .. code-block:: bash

      git clone https://github.com/couchbaselabs/agent-catalog

4. Navigate to the ``agent-catalog`` directory and run :code:`make`.
   This will a) create a new virtual environment using Poetry and b) install all required packages and CLI tools.

5. Activate your newly created virtual environment using the outputs of :code:`make activate` or
   :code:`poetry env activate`.
   If you do not want to copy-and-paste the output, you can run the command with :code:`eval`:

   .. code-block:: bash

      eval $(poetry env activate)

   If your environment has been successfully activated, you should see ``(Activated)`` after running
   :code:`poetry env list`.

   .. code-block:: bash

      poetry env list
      agent-catalog-UEfqTvAT-py3.13 (Activated)

   .. note::

      Note that you must activate your environment before running any :code:`agentc` commands!

   If your environment has been activated properly, you should see the following output:

   .. click:run::
      from agentc_cli.main import agentc
      invoke(agentc)

6. If you are interested in building a ``.whl`` file (for later use in ``.whl``-based installation in other projects),
   run the following command:

   .. code-block:: bash

      cd libs/agentc
      poetry build

Installing from Source (with Anaconda)
--------------------------------------

1. Make sure you have :code:`python3.12` and
   `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`_ installed!

2. Create a new virtual environment with Anaconda and subsequently activate your environment.
   Again, you must activate your environment before running any :code:`agentc` commands!

   .. code-block:: bash

      conda create -n my_agentc_env python=3.12
      conda activate my_agentc_env

3. Navigate to this directory and install Agent Catalog with :code:`pip`:

   .. code-block:: bash

      cd agent-catalog

      # Install the agentc package.
      pip install libs/agentc

   If you are interested in developing with LangChain or LangGraph, install the helper ``agentc_langchain`` package
   and/or ``agentc_langgraph`` package with the command(s) below:

   .. code-block:: bash

      pip install libs/agentc_integrations/langchain
      pip install libs/agentc_integrations/langgraph

   Similarly, for LlamaIndex Developers:

   .. code-block:: bash

      pip install libs/agentc_integrations/llamaindex
