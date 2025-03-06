.. role:: python(code)
   :language: python

Agent Catalog Configuration
===========================

Agent Catalog can be configured on a per-instance-basis (for :python:`Catalog` and :python:`Scope` instances) **or**
globally using environment variables.
If you have a ``.env`` file in the same working directory as Agent Catalog, the environment variables will additionally
be read from there.


.. autopydantic_model:: agentc_core.config.config.RemoteCatalogConfig
.. autopydantic_model:: agentc_core.config.config.LocalCatalogConfig
.. autopydantic_model:: agentc_core.config.config.EmbeddingModelConfig
.. autopydantic_model:: agentc_core.config.config.CommandLineConfig
.. autopydantic_model:: agentc_core.config.config.VersioningConfig
.. autopydantic_model:: agentc_core.config.config.Config
