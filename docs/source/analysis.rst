.. role:: python(code)
   :language: python

.. role:: sql(code)
   :language: sql

Log Analysis
============

On this page, we detail how Couchbase enables easy and efficient ad-hoc analysis of your logs.

.. tip::

    Logs are also stored locally (by default) in the :file:`./agent-activity` directory and you are free to process them
    out of Couchbase, but we recommend leveraging a database purposed for Big Data (e.g., Couchbase) to deliver insights
    about your application's performance faster.

:sql:`logs` Collection
----------------------

Agent Catalog maintains a collection of log entries whose schema is identical to that of the Pydantic model
`here <log.html#schema-of-logs>`__.
Agent application analysts are free to directly query the :sql:`logs` collection *or* any of the views in the
following section.
For completeness, we show the use of the standard :python:`couchbase` package to directly query the :sql:`logs`
collection from the Analytics Service below:

.. code-block:: python

    import couchbase.auth
    import couchbase.cluster
    import couchbase.options

    auth = couchbase.auth.PasswordAuthenticator(
        username="Administrator",
        password="password"
    )
    cluster = couchbase.cluster.Cluster(
        "couchbase:127.0.0.1",
        options=couchbase.options.ClusterOptions(auth)
    )

    query = cluster.analytics_query("""
        FROM
            [MY_BUCKET].agent_activity.logs l
        SELECT
            l.*
        LIMIT 100;
    """)
    for result in query:
        print(result)


Views Over :sql:`logs`
----------------------

Agent Catalog (as of date) provides two sets of non-materialized views: one for users with the Analytics Service
enabled on their cluster and another for users who would prefer using the Query Service (in conjunction with a
primary index).
The former uses standard view syntax (e.g., :sql:`FROM agent_activity.Sessions AS s`) while the latter uses
function syntax (e.g., :sql:`FROM agent_activity.Sessions() AS s`) [1]_.

:sql:`Sessions` View
^^^^^^^^^^^^^^^^^^^^

All :py:class:`Span` instances are uniquely identified by a name and a runtime identifier :python:`session`.
The :sql:`Sessions` view provides one record per session, enabling analysts to reason about their application per "run"
(e.g., per conversation).

Each session record contains:

i) the session ID :sql:`sid`,

ii) the session start time :sql:`start_t`,

iii) the catalog version :sql:`cid`, and

iv) a list of content entries :sql:`content`.

The :sql:`content` field details all events that occurred during the session (e.g., the user's messages, the
response to the user, the internal "thinking" performed by some agent, etc...).
Below we give Python code snippets (assuming the existence of a Couchbase :python:`couchbase.cluster.Cluster` instance
named :python:`cluster`) to access this view for both the Analytics Service and the Query Service:

.. tab-set::

    .. tab-item:: Analytics Service

        .. code-block:: python

            bucket = "MY_BUCKET"
            query = cluster.analytics_query(f"""
                FROM
                    `{bucket}`.agent_activity.Sessions s
                SELECT
                    s.sid,
                    s.start_t,
                    s.cid,
                    s.content
                LIMIT 10;
            """)
            for result in query:
                print(result)

    .. tab-item:: Query Service

        .. code-block:: python

            bucket = "MY_BUCKET"
            query = cluster.query(f"""
                FROM
                    `{bucket}`.agent_activity.Sessions() s
                SELECT
                    s.sid,
                    s.start_t,
                    s.cid,
                    s.content
                LIMIT 10;
            """)
            for result in query:
                print(result)


For convenience, we also provide a UDF (for both the Query Service and the Analytics Service) :sql:`LastSession()` that
enables users to add the following to their :sql:`WHERE` clause:

.. code-block:: sql

    WHERE sid = `[MY_BUCKET]`.agent_activity.LastSession()

:sql:`Exchanges` View
^^^^^^^^^^^^^^^^^^^^^

More often than not, we are interested in events that happen between a user giving some input and an assistant's
response.
The :sql:`Exchanges` view provides one record per exchange (i.e., the period between user input and an
assistant's response) in a given session.
Each exchange record contains:

i) the session ID :sql:`sid`,

ii) the user's input :sql:`input`,

iii) an assistant's response :sql:`output`, and

iv) all intermediate logs :sql:`content` between the input and output events (e.g., the messages sent to the
    LLMs, the tools executed, etc...).

Below we give code snippets to access the most recent exchange for both the Analytics Service and the Query Service:

.. tab-set::

    .. tab-item:: Analytics Service

        .. code-block:: python

            bucket = "MY_BUCKET"
            query = cluster.analytics_query(f"""
                FROM
                    `{bucket}`.agent_activity.Exchanges e
                SELECT
                    e.sid,
                    e.input,
                    e.output,
                    e.content
                ORDER BY
                    e.output.timestamp DESC
                LIMIT 1;
            """)
            for result in query:
                print(result)

    .. tab-item:: Query Service

        .. code-block:: python

            bucket = "MY_BUCKET"
            query = cluster.query(f"""
                FROM
                    `{bucket}`.agent_activity.Exchanges() e
                SELECT
                    e.sid,
                    e.input,
                    e.output,
                    e.content
                ORDER BY
                    e.output.timestamp DESC
                LIMIT 1;
            """)
            for result in query:
                print(result)

:sql:`ToolInvocations` View
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To view tool calls *with* their corresponding tool results, many frameworks will log a :python:`tool_call_id` value.
Other frameworks may choose to leave out this :python:`tool_call_id` value, but tool result -- tool call pairs can be
found by reasoning about their temporal relation to one another.
The :sql:`ToolInvocations` view provides one record per :python:`{tool_call, tool_result}` pair and takes the
:sql:`UNION` of both aforementioned approaches.
Each tool-invocation record contains:

i) the session ID :sql:`sid`,

ii) the tool call entry :sql:`tool_call`, and

iii) the corresponding tool result entry :sql:`tool_result`.

Below we give code snippets to access the most recent tool invocation for both the Analytics Service and the Query
Service:

.. tab-set::

    .. tab-item:: Analytics Service

        .. code-block:: python

            bucket = "MY_BUCKET"
            query = cluster.analytics_query(f"""
                FROM
                    `{bucket}`.agent_activity.ToolInvocations ti
                SELECT
                    ti.sid,
                    ti.tool_call,
                    ti.tool_result
                ORDER BY
                    ti.tool_result.timestamp DESC
                LIMIT 1;
            """)
            for result in query:
                print(result)

    .. tab-item:: Query Service

        .. code-block:: python

            query = cluster.query(f"""
                FROM
                    `{bucket}`.agent_activity.ToolInvocations() ti
                SELECT
                    ti.sid,
                    ti.tool_call,
                    ti.tool_result
                ORDER BY
                    ti.tool_result.timestamp DESC
                LIMIT 1;
            """)
            for result in query:
                print(result)

.. [1] The Query Service is targeted towards more operational use cases and thus does not support non-materialized views
       like the Analytics Service.
       The Query Service does support user-defined-functions (UDFs) though, thus all Agent Catalog Analytics Service
       views can also be expressed using Query Service UDFs.




