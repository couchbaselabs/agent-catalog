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
       The name of the bucket where your catalog and all logs are/will be stored.


Optional Environment Variables
------------------------------

``AGENT_CATALOG_ACTIVITY``
       TODO

``AGENT_CATALOG_CATALOG``
       TODO

``AGENT_CATALOG_INTERACTIVE``
       TODO

``AGENT_CATALOG_DEBUG``
       TODO

``AGENT_CATALOG_SNAPSHOT``
       TODO

``AGENT_CATALOG_PROVIDER_OUTPUT``
       TODO

``AGENT_CATALOG_AUDITOR_OUTPUT``
       TODO

``AGENT_CATALOG_EMBEDDING_MODEL``
       TODO
