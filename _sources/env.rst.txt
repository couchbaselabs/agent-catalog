.. role:: python(code)
   :language: python

Agent Catalog Environment Variables
===================================

Agent Catalog can be configured globally using the environment variables defined in this section.
If you have a ``.env`` file in the same working directory as Agent Catalog, the environment variables will additionally
be read from there.


Mandatory Environment Variables
-------------------------------

``AGENT_CATALOG_CONN_STRING``
    The connection string for your Couchbase cluster.
    This can be set to ``localhost`` if you are hosting the cluster locally or obtained from Capella if you are
    using the cloud-based service.
    For more information on connection strings, refer to the documentation
    `here <https://docs.couchbase.com/python-sdk/current/howtos/managing-connections.html#connection-strings>`_.

``AGENT_CATALOG_USERNAME``
    The username of the account/database access key used to access your Couchbase cluster.

``AGENT_CATALOG_PASSWORD``
    The password of the account/database access key used to access your Couchbase cluster

``AGENT_CATALOG_BUCKET``
    The name of the bucket where your catalog and all audit logs are/will be stored.


Optional Environment Variables
------------------------------

``AGENT_CATALOG_ACTIVITY``
    The location on your filesystem that denotes where the local audit logs are stored.

``AGENT_CATALOG_CATALOG``
    The location on your filesystem that denotes where the local catalogs (i.e., the ``tool-catalog.json`` and
    ``prompt-catalog.json`` files) are stored.

``AGENT_CATALOG_INTERACTIVE``
    A boolean flag that denotes whether the Agent Catalog CLI should run in interactive mode.
    If set to :python:`True`, the CLI will prompt the user for input.
    If set to :python:`False`, the CLI will not prompt the user for input (useful for scripting).

``AGENT_CATALOG_DEBUG``
    A boolean flag that denotes whether Agent Catalog should run in debug mode.
    If set to :python:`True`, both the SDK and the CLI will display debug messages.

``AGENT_CATALOG_SNAPSHOT``
    The version of the catalog that the Agent Catalog SDK should use when serving tools and prompts.
    By default, the SDK will use the latest version of the catalog.

``AGENT_CATALOG_PROVIDER_OUTPUT``
    The location on your filesystem where the generated tool code of :python:`agentc.Provider` will write and serve
    from.
    By default, the :python:`agentc.Provider` class does not write the generated code to disk.
    If this parameter is set, the generated code will be written to the specified location.

``AGENT_CATALOG_AUDITOR_OUTPUT``
    The location + filename of the audit logs that the :python:`agentc.Auditor` will write to.
    By default, the :python:`agentc.Auditor` class will write and rotate logs in the :file:`./agent-activity` directory.

``AGENT_CATALOG_EMBEDDING_MODEL``
    The embedding model that Agent Catalog will use when indexing and querying tools and prompts.
    This *must* be a valid embedding model that is supported by the :python:`sentence_transformers.SentenceTransformer`
    class.
    By default, the ``sentence-transformers/all-MiniLM-L12-v2`` model is used.
