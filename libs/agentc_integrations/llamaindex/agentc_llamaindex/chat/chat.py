import typing

from agentc_core.activity import Span
from llama_index.core import BaseCallbackHandler
from llama_index.core.callbacks import CBEventType


# TODO (GLENN): Finish implementing this class.
class Callback(BaseCallbackHandler):
    def __init__(
        self,
        span: Span,
        event_starts_to_ignore: list[CBEventType] = None,
        event_ends_to_ignore: list[CBEventType] = None,
    ) -> None:
        super().__init__(event_starts_to_ignore or list(), event_ends_to_ignore or list())

        # We'll use a stack to store our active traces.
        self.active_traces: list[Span] = list()
        self.root_span = span

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: typing.Optional[dict[str, typing.Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: typing.Any,
    ) -> str:
        # scope: Span = self.active_traces[-1]
        raise NotImplementedError("Not implemented")

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: typing.Optional[dict[str, typing.Any]] = None,
        event_id: str = "",
        **kwargs: typing.Any,
    ) -> None:
        raise NotImplementedError("Not implemented")

    def start_trace(self, trace_id: typing.Optional[str] = None) -> None:
        self.active_traces += [self.root_span.new(name="start_trace", trace_id=trace_id)]
        self.active_traces[-1].enter()

    def end_trace(
        self,
        trace_id: typing.Optional[str] = None,
        trace_map: typing.Optional[dict[str, typing.List[str]]] = None,
    ) -> None:
        self.active_traces.pop().exit()
