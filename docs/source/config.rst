.. role:: python(code)
   :language: python

Agent Catalog Configuration
===========================

Agent Catalog can be configured 1) on a per-instance-basis (for :python:`Catalog` and :python:`Span` instances),
2) globally using environment variables, or 3) globally using a :file:`.env` file.

.. attention::

    Environment variables will always take priority over values loaded from a :file:`.env` file.

.. autopydantic_model:: agentc_core.config.config.Config
    :show-inheritance:

.. autopydantic_model:: agentc_core.config.config.RemoteCatalogConfig
.. autopydantic_model:: agentc_core.config.config.LocalCatalogConfig
.. autopydantic_model:: agentc_core.config.config.EmbeddingModelConfig
.. autopydantic_model:: agentc_core.config.config.CommandLineConfig
.. autopydantic_model:: agentc_core.config.config.VersioningConfig
