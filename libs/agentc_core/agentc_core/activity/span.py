import couchbase.exceptions
import functools
import logging
import pydantic
import textwrap
import typing
import uuid

from .logger import ChainLogger
from .logger import DBLogger
from .logger import LocalLogger
from agentc_core.activity.models.content import BeginContent
from agentc_core.activity.models.content import Content
from agentc_core.activity.models.content import EndContent
from agentc_core.activity.models.content import KeyValueContent
from agentc_core.activity.models.log import Log
from agentc_core.config import LocalCatalogConfig
from agentc_core.config import RemoteCatalogConfig
from agentc_core.version import VersionDescriptor

logger = logging.getLogger(__name__)


class Span(pydantic.BaseModel):
    """A structured logging context for agent activity.

    .. card:: Class Description

        A :py:class:`Span` instance belongs to a tree of other :py:class:`Span` instances, whose root is a
        :py:class:`GlobalSpan` instance that is constructed using the :py:meth:`Catalog.Span` method.

        .. attention::

            Spans should never be created directly (via constructor), as logs generated by the span must always be
            associated with a catalog version and some application structure.

        Below we illustrate how a tree of :py:class:`Span` instances is created:

        .. code-block:: python

            import agentc
            catalog = agentc.Catalog()
            root_span = catalog.Span(name="root")
            child_1_span = root_span.new(name="child_1")
            child_2_span = root_span.new(name="child_2")

        In practice, you'll likely use different spans for different agents and/or different tasks.
        Below we give a small LangGraph example using spans for different agents:

        .. code-block:: python

            import agentc
            import langgraph.graph

            catalog = agentc.Catalog()
            root_span = catalog.Span(name="flight_planner")

            def front_desk_agent(...):
                with root_span.new(name="front_desk_agent") as front_desk_span:
                    ...

            def route_finding_agent(...):
                with root_span.new(name="route_finding_agent") as route_finding_span:
                    ...

            workflow = langgraph.graph.StateGraph()
            workflow.add_node("front_desk_agent", front_desk_agent)
            workflow.add_node("route_finding_agent", route_finding_agent)
            workflow.set_entry_point("front_desk_agent")
            workflow.add_edge("front_desk_agent", "route_finding_agent")
            ...

    """

    class Identifier(pydantic.BaseModel):
        """The unique identifier for a :py:class:`Span`.

        .. card:: Class Description

            A :py:class:`Span` is uniquely identified by two parts:

            1. an application-defined multipart name and...
            2. a session identifier unique to each run of the application.
        """

        model_config = pydantic.ConfigDict(frozen=True)

        name: list[str]
        """ The name of the :py:class:`Span`.

        Names are built up from the root of the span tree to the leaf, thus the first element of :py:attr:`name` is the
        name of the root and the last element is the name of the current span (i.e., the leaf).
        """

        session: str
        """ The session identifier of the :py:class:`Span`.

        Sessions must be unique to each run of the application.
        By default, we generate these as UUIDs (see :py:attr:`GlobalSpan.session`).
    """

    logger: typing.Callable[..., Log]
    """ Method which handles the logging implementation. """

    name: str
    """ Name to bind to each message logged within this span. """

    parent: "Span" = None
    """ Parent span of this span (i.e., the span that had :py:meth:`new` called on it). """

    state: typing.Any = None
    """ A JSON-serializable object that will be logged on entering and exiting this span. """

    iterable: typing.Optional[bool] = False
    """ Flag to indicate whether or not this span should be iterable. """

    kwargs: typing.Optional[dict[str, typing.Any]] = None
    """ Annotations to apply to all messages logged within this span. """

    _logs: list[Log] = None

    @pydantic.model_validator(mode="after")
    def _initialize_iterable_logger(self) -> typing.Self:
        if self.iterable:
            logger.debug(f"Iterable span requested for {str(self.identifier.name)}.")
            self._logs = list()

            # The logs captured here (and this instance's children) belong to this specific span.
            # The "iterable" field itself is not propagated to children.
            original_logger = self.logger

            @functools.wraps(original_logger)
            def iterable_logger(*args, **kwargs) -> typing.Callable[..., Log]:
                log = original_logger(*args, **kwargs)
                self._logs.append(log)
                return log

            self.logger = iterable_logger

        return self

    def new(self, name: str, state: typing.Any = None, iterable: bool = False, **kwargs) -> "Span":
        """Create a new span under the current :py:class:`Span`.

        .. card:: Method Description

            Spans require a name and a session (see :py:attr:`identifier`).
            Aside from :py:attr:`name`, :py:attr:`state`, and :py:attr:`iterable`, you can also pass additional keywords
            that will be applied as annotations to each :py:meth:`log` call within a span.
            As an example, the following code illustrates the use of :py:attr:`kwargs` to add a span-wide "alpha"
            annotation:

            .. code-block:: python

                import agentc
                catalog = agentc.Catalog()
                root_span = catalog.Span(name="flight_planner")
                with root_span.new(name="find_airports_task", alpha="SDGD") as child_span:
                    child_span.log(content=agentc.span.UserContent(value="Hello, world!", "beta": "412d"))

            The example code above will generate the three logs below (for brevity, we only show the ``content`` and
             ``annotations`` fields):

            .. code-block:: json

                { "content": { "kind": "begin" }, "annotations": { "alpha": "SDGD"} }
                { "content": { "kind": "user", "value": "Hello, world!" },
                  "annotations": { "alpha": "SDGD", "beta": "412d" } }
                { "content" : { "kind": "end" }, "annotations": { "alpha": "SDGD" } }

        :param name: The name of the span.
        :param state: The starting state of the span. This will be recorded upon entering and exiting the span.
        :param iterable: Whether this new span should be iterable. By default, this is :python:`False`.
        :param kwargs: Additional annotations to apply to the span.
        :return: A new :py:class:`Span` instance.
        """

        # **kwargs take precedence over self.kwargs.
        if self.kwargs is not None and len(kwargs) > 0:
            new_kwargs = {**self.kwargs, **kwargs}
        elif self.kwargs is not None:
            new_kwargs = self.kwargs
        elif len(kwargs) > 0:
            new_kwargs = kwargs
        else:
            new_kwargs = None

        return Span(
            logger=self.logger,
            name=name,
            parent=self,
            iterable=iterable,
            state=state or self.state,
            kwargs=new_kwargs,
        )

    def log(self, content: Content, **kwargs):
        """Accept some content (with optional annotations specified by :python:`kwargs`) and generate a
        corresponding log entry.

        .. card:: Method Description

            The heart of the :py:class:`Span` class is the :py:meth:`log` method.
            This method is used to log events that occur within the span.
            Users can capture events that occur in popular frameworks like LangChain and LlamaIndex using our helper
            packages (see :py:mod:`agentc_langchain`, :py:mod:`agentc_langgraph`, and :py:mod:`agentc_llamaindex`) but
            must use those packages in conjunction with this :py:meth:`log` method to capture the full breadth of their
            application's activity.
            See `here <log.html>`__ for a list of all available log content types.

            Users can also use Python's ``[]`` syntax to write arbitrary JSON-serializable content as a key-value
            (:py:class:`KeyValueContent`) pair.
            This is useful for logging arbitrary data like metrics during evaluations.
            In the example below, we illustrate an example of a system-wide evaluation suite that uses this ``[]``
            syntax:

            .. code-block:: python

                import my_agent_app
                import my_output_evaluator
                import agentc

                catalog = agentc.Catalog()
                evaluation_span = catalog.Span(name="evaluation_suite")
                with open("my-evaluation-suite.json") as fp:
                    for i, line in enumerate(fp):
                        with evaluation_span.new(name=f"evaluation{i}") as span:
                            output = my_agent_app(span)
                            span["positive_sentiment"] = my_output_evaluator.positive(output)
                            span.log(
                                content={
                                    "kind": "key-value",
                                    "key": "negative_sentiment",
                                    "value": my_output_evaluator.negative(output)
                                    },
                                alpha="SDGD"
                            )

            All keywords passed to the :py:meth:`log` method will be applied as annotations to the log entry.
            In the example above, the ``alpha`` annotation is applied only to the second log entry.
            For span-wide annotations, use the :py:attr:`kwargs` attribute on :py:meth:`new`.

        :param content: The content to log.
        :param kwargs: Additional annotations to apply to the log.
        """
        new_kwargs = {**self.kwargs, **kwargs} if self.kwargs is not None else kwargs
        identifier: Span.Identifier = self.identifier
        _log = self.logger(content=content, session_id=identifier.session, span_name=identifier.name, **new_kwargs)
        if self.iterable:
            self._logs.append(_log)

    @pydantic.computed_field
    @property
    def identifier(self) -> "Span.Identifier":
        """A unique identifier for this span."""
        name_stack = [self.name]
        working = self
        while working.parent is not None:
            name_stack += [working.parent.name]
            working = working.parent
        return Span.Identifier(name=list(reversed(name_stack)), session=working.session)

    def enter(self) -> typing.Self:
        """Record a :py:class:`BeginContent` log entry for this span.

        .. card:: Method Description

            The :py:meth:`enter` method is to denote the start of the span (optionally logging the incoming state if
            specified).
            This method is also called when entering the span using the :python:`with` statement.
            In the example below, :py:meth:`enter` is called (implicitly).

            .. code-block:: python

                import agentc

                catalog = agentc.Catalog()
                incoming_state = {"flights": []}
                with catalog.Span(name="flight_planner", state=incoming_state) as span:
                    flight_planner_implementation()

            On entering the context, one log is generated possessing the content below:

            .. code-block:: json

                { "kind": "begin", "state": {"flights": []} }

        """
        self.log(content=BeginContent() if self.state is None else BeginContent(state=self.state))
        return self

    def exit(self):
        """Record a :py:class:`EndContent` log entry for this span.

        .. card:: Method Description

            The :py:meth:`exit` method is to denote the end of the span (optionally logging the outgoing state if
            specified).
            This method is also called when exiting the span using the :python:`with` statement *successfully*.
            In the example below, :py:meth:`exit` is called (implicitly).

            .. code-block:: python

                import agentc

                catalog = agentc.Catalog()
                incoming_state = {"flights": []}
                with catalog.Span(name="flight_planner", state=incoming_state) as span:
                    ... = flight_planner_implementation(...)
                    incoming_state["flights"] = [{"flight_number": "AA123", "status": "on_time"}]

            On exiting the context, one log is generated possessing the content below:

            .. code-block:: json

                { "kind": "end", "state": {"flights": [{"flight_number": "AA123", "status": "on_time"}]} }

        .. note::

            The :python:`state` of the span must be JSON-serializable **and** must be mutated in-place.
            If you are working with immutable state objects, you must set the :py:attr:`state` attribute before exiting
            the span (i.e., before the :python:`with` statement exits or with :py:meth:`exit` explicitly).

            .. code-block:: python

                import agentc

                catalog = agentc.Catalog()
                immutable_incoming_state = {"flights": []}
                with catalog.Span(name="flight_planner", state=incoming_state) as span:
                    ... = flight_planner_implementation(...)
                    span.state = {"flights": [{"flight_number": "AA123", "status": "on_time"}]}
        """
        self.log(content=EndContent() if self.state is None else EndContent(state=self.state))

    def logs(self) -> typing.Iterable[Log]:
        """Return the logs generated by the tree of :py:class:`Span` nodes rooted from this :py:class:`Span` instance.

        .. card:: Method Description

            The :py:meth:`logs` method returns an iterable of all logs generated within the span.
            This method is also called (implicitly) when iterating over the span (e.g., using a :python:`for` loop).
            To use this method, you must set the :py:attr:`iterable` attribute to True when instantiating the span:

            .. code-block:: python

                import agentc

                catalog = agentc.Catalog()
                span = catalog.Span(name="flight_planner", iterable=True)
                for log in span:
                    match log.content.kind:
                        case "begin":
                            ...

        .. tip::

            Generally, this method should only be used for debugging purposes.
            This method will keep **all** logs generated by the span in memory.
            To perform efficient aggregate analysis of your logs, consider querying the ``agent_activity.logs``
            collection in your Couchbase cluster using SQL++ instead.

        """
        if not self.iterable:
            raise ValueError("This span is not iterable. To iterate over logs, set 'iterable'=True on instantiation.")
        return self._logs

    def __enter__(self):
        return self.enter()

    def __setitem__(self, key: str, value: typing.Any):
        self.log(content=KeyValueContent(key=key, value=value))

    def __exit__(self, exc_type, exc_val, exc_tb):
        # We will only record this transition if we are exiting cleanly.
        if all(x is None for x in [exc_type, exc_val, exc_tb]):
            self.exit()

    def __iter__(self):
        if not self.iterable:
            raise ValueError("This span is not iterable. To iterate over logs, set 'iterable'=True on instantiation.")
        yield from self._logs


class GlobalSpan(Span):
    """An auditor of various events (e.g., LLM completions) given a catalog."""

    # Note: this is more of a composite type rather than a union type.
    config: typing.Union[LocalCatalogConfig, RemoteCatalogConfig]
    """ Config (configuration) instance associated with this activity. """

    session: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex, frozen=True)
    """ The run (alternative: session) that this span is associated with. """

    version: VersionDescriptor = pydantic.Field(frozen=True)
    """ Catalog version to bind all messages logged within this auditor. """

    logger: typing.Optional[typing.Callable] = None
    _local_logger: LocalLogger = None
    _db_logger: DBLogger = None
    _chain_logger: ChainLogger = None

    @pydantic.model_validator(mode="after")
    def _find_local_activity(self) -> typing.Self:
        if self.config.activity_path is None:
            try:
                # Note: this method sets the self.config.activity_path attribute if found.
                self.config.ActivityPath()
            except ValueError as e:
                logger.debug(
                    f"Local activity (folder) not found while trying to initialize a Span instance. "
                    f"Swallowing exception {str(e)}."
                )
        return self

    @pydantic.model_validator(mode="after")
    def _initialize_auditor(self) -> typing.Self:
        if self.config.activity_path is None and self.config.conn_string is None:
            error_message = textwrap.dedent("""
                Could not initialize a local or remote auditor!
                If this is a new project, please run the command `agentc init` before instantiating an auditor.
                If you are intending to use a remote-only auditor, please ensure that all of the relevant variables
                (i.e., conn_string, username, password, and bucket) are set.
            """)
            logger.debug(error_message)
            raise ValueError(error_message)

        # Finally, instantiate our auditors.
        if self.config.activity_path is not None:
            self._local_logger = LocalLogger(cfg=self.config, catalog_version=self.version, **self.kwargs)
        if self.config.conn_string is not None:
            try:
                self._db_logger = DBLogger(cfg=self.config, catalog_version=self.version, **self.kwargs)
            except (couchbase.exceptions.CouchbaseException, ValueError) as e:
                logger.warning(
                    f"Could not connect to the Couchbase cluster. "
                    f"Skipping remote auditor and swallowing exception {str(e)}."
                )
                self._db_logger = None

        # If we have both a local and remote auditor, we'll use both.
        if self._local_logger is not None and self._db_logger is not None:
            logger.info("Using both a local auditor and a remote auditor.")
            self._chain_logger = ChainLogger(self._local_logger, self._db_logger, **self.kwargs)
            self.logger = self._chain_logger.log
        elif self._local_logger is not None:
            logger.info("Using a local auditor (a connection to a remote auditor could not be established).")
            self.logger = self._local_logger.log
        elif self._db_logger is not None:
            logger.info("Using a remote auditor (a local auditor could not be instantiated).")
            self.logger = self._db_logger.log
        else:
            # We should never reach this point (this error is handled above).
            raise ValueError("Could not instantiate an auditor.")
        return self

    def new(self, name: str, state: typing.Any = None, iterable: bool = False, **kwargs) -> Span:
        """Create a new span under the current :py:class:`GlobalSpan`.

        :param name: The name of the span.
        :param state: The starting state of the span. This will be recorded upon entering and exiting the span.
        :param iterable: Whether this new span should be iterable.
        :param kwargs: Additional annotations to apply to the span.
        :return: A new :py:class:`Span` instance.
        """
        return Span(logger=self.logger, name=name, parent=self, state=state, iterable=iterable, kwargs=kwargs)
