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

1. Make sure you have :command:`python3.12` and `poetry <https://python-poetry.org/docs/#installation>`__ installed!

2. Make sure you have :command:`make` installed!
   For Mac-based installations, see `here <https://formulae.brew.sh/formula/make>`__.
   For Windows-based installations, see `here <https://gnuwin32.sourceforge.net/packages/make.htm>`__.
   For Ubuntu-based installations, see `here <https://www.geeksforgeeks.org/how-to-install-make-on-ubuntu/>`__.

3. Clone this repository.

   .. code-block:: ansi-shell-session

      $ git clone https://github.com/couchbaselabs/agent-catalog

4. Navigate to the ``agent-catalog`` directory and run :command:`make`.
   This will a) create a new virtual environment using Poetry and b) install all required packages and CLI tools.

5. Activate your newly created virtual environment using the outputs of :code:`make activate` or
   :code:`poetry env activate`.
   If you do not want to copy-and-paste the output, you can run the command with :command:`eval`:

   .. code-block:: ansi-shell-session

      $ eval $(poetry env activate)

   If your environment has been successfully activated, you should see ``(Activated)`` after running
   :code:`poetry env list`.

   .. code-block:: ansi-shell-session

      $ poetry env list
      agent-catalog-UEfqTvAT-py3.13 (Activated)

   .. note::

      Note that you must activate your environment before running any :command:`agentc` commands!

   If your environment has been activated properly, you should see the following output:

   .. click:run::
      from agentc_cli.main import agentc
      invoke(agentc)

6. If you are interested in building a ``.whl`` file (for later use in ``.whl``-based installation in other projects),
   run the following command:

   .. code-block:: ansi-shell-session

      $ cd libs/agentc
      $ poetry build

Installing from Source (with Anaconda)
--------------------------------------

1. Make sure you have :command:`python3.12` and
   `conda <https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`__ installed!

2. Create a new virtual environment with Anaconda and subsequently activate your environment.
   Again, you must activate your environment before running any :command:`agentc` commands!

   .. code-block:: ansi-shell-session

      $ conda create -n my_agentc_env python=3.12
      $ conda activate my_agentc_env

3. Navigate to this directory and install Agent Catalog with :command:`pip`:

   .. code-block:: ansi-shell-session

      $ cd agent-catalog

      $ # Install the agentc package.
      $ pip install libs/agentc

   If you are interested in developing with LangChain or LangGraph, install the helper ``agentc_langchain`` package
   and/or ``agentc_langgraph`` package with the command(s) below:

   .. code-block:: ansi-shell-session

      $ pip install libs/agentc_integrations/langchain
      $ pip install libs/agentc_integrations/langgraph

   Similarly, for LlamaIndex Developers:

   .. code-block:: ansi-shell-session

      $ pip install libs/agentc_integrations/llamaindex
