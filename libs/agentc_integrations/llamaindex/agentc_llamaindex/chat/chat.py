import llama_index.core.llms.callbacks
import llama_index.core.tools
import logging
import pydantic
import typing
import uuid

from agentc_core.activity import Span
from agentc_core.analytics import ToolCallContent
from agentc_core.analytics import ToolResultContent
from agentc_core.analytics.log import Kind
from llama_index.core import BaseCallbackHandler
from llama_index.core.callbacks import CBEventType
from llama_index.core.callbacks import EventPayload

logger = logging.getLogger(__name__)

_TYPE_TO_KIND_MAPPING = {
    llama_index.core.llms.MessageRole.SYSTEM: Kind.System,
    llama_index.core.llms.MessageRole.USER: Kind.Human,
    llama_index.core.llms.MessageRole.ASSISTANT: Kind.Assistant,
    llama_index.core.llms.MessageRole.TOOL: Kind.Tool,
    llama_index.core.llms.MessageRole.FUNCTION: Kind.Tool,
    llama_index.core.llms.MessageRole.MODEL: Kind.LLM,
    llama_index.core.llms.MessageRole.CHATBOT: Kind.Assistant,
}


def _get_kind_from_message(message: llama_index.core.llms.ChatMessage) -> Kind:
    return _TYPE_TO_KIND_MAPPING[message.role]


class Callback(BaseCallbackHandler):
    class TraceNode(pydantic.BaseModel):
        span: Span
        children: dict[llama_index.core.llms.MessageRole, "Callback.TraceNode"]

    def __init__(
        self,
        span: Span,
        event_starts_to_ignore: list[CBEventType] = None,
        event_ends_to_ignore: list[CBEventType] = None,
    ) -> None:
        super().__init__(event_starts_to_ignore or list(), event_ends_to_ignore or list())

        # We'll use a stack to store our active traces.
        self.active_traces: list[Callback.TraceNode] = list()
        self.root_span = span

    @staticmethod
    def _handle_unknown_payload(span: Span, payload: dict[str, typing.Any], **kwargs) -> None:
        logger.debug("Encountered unknown payload %s.", payload)
        for key, value in payload.items():
            try:
                span.log(kind=Kind.System, content=value, **kwargs)
            except Exception as e:
                logger.error("Error logging payload %s!", key)
                logger.error(e)

    @staticmethod
    def _handle_payload(span: Span, event_type: CBEventType, payload: dict[str, typing.Any]) -> None:
        logger.debug("Handling event of type %s.", event_type)
        unhandled_payloads = set(payload.keys())

        # Determine any 'extraneous' fields in the payload (that will be logged as annotations).
        annotations = dict()
        if EventPayload.ADDITIONAL_KWARGS in payload:
            if len(payload[EventPayload.ADDITIONAL_KWARGS]) > 0:
                annotations["additional_kwargs"] = payload[EventPayload.ADDITIONAL_KWARGS]
            unhandled_payloads.remove(EventPayload.ADDITIONAL_KWARGS)
        if EventPayload.SERIALIZED in payload:
            annotations["serialized"] = payload[EventPayload.SERIALIZED]
            unhandled_payloads.remove(EventPayload.SERIALIZED)

        # TODO (GLENN): Support more than just LLM and FUNCTION_CALL events.
        match event_type:
            case CBEventType.LLM:
                if EventPayload.PROMPT in payload:
                    span.log(kind=Kind.System, content=payload[EventPayload.PROMPT], **annotations)
                    unhandled_payloads.remove(EventPayload.PROMPT)

                # Note: we shouldn't expect both MESSAGES and PROMPT to exist at the same time...
                if EventPayload.MESSAGES in payload:
                    for message in payload[EventPayload.MESSAGES]:
                        # This is just to get some typing for our IDEs.
                        message: llama_index.core.llms.ChatMessage = message
                        span.log(kind=_get_kind_from_message(message), content=message.content, **annotations)
                    unhandled_payloads.remove(EventPayload.MESSAGES)

                if EventPayload.COMPLETION in payload:
                    completion_payload: llama_index.core.llms.CompletionResponse = payload[EventPayload.COMPLETION]
                    span.log(
                        kind=Kind.LLM,
                        content=completion_payload.text,
                        logprobs=completion_payload.logprobs,
                        delta=completion_payload.delta,
                        **annotations,
                    )
                    unhandled_payloads.remove(EventPayload.COMPLETION)

                # Note: we shouldn't expect both COMPLETION and RESPONSE to exist at the same time...
                if EventPayload.RESPONSE in payload:
                    response_payload: llama_index.core.llms.ChatResponse = payload[EventPayload.RESPONSE]
                    span.log(
                        kind=Kind.LLM,
                        content=response_payload.message.content,
                        meta=response_payload.message,
                        logprobs=response_payload.logprobs,
                        delta=response_payload.delta,
                        **annotations,
                    )
                    unhandled_payloads.remove(EventPayload.RESPONSE)

                # For all other fields, we will log them as SYSTEM events.
                Callback._handle_unknown_payload(
                    span, {key: value for key, value in payload.items() if key in unhandled_payloads}, **annotations
                )

            case CBEventType.FUNCTION_CALL:
                # We will generate our own unique ID for each tool call.
                tool_call_id = uuid.uuid4().hex
                if EventPayload.TOOL in payload and EventPayload.FUNCTION_CALL in payload:
                    tool: llama_index.core.tools.ToolMetadata = payload[EventPayload.TOOL]
                    func: dict[str, typing.Any] = payload[EventPayload.FUNCTION_CALL]
                    span.log(
                        kind=Kind.Tool,
                        content=ToolCallContent(
                            tool_name=tool.name, tool_args=func, tool_call_id=tool_call_id, status="success", extra=tool
                        ),
                    )
                    unhandled_payloads.remove(EventPayload.FUNCTION_CALL)
                    unhandled_payloads.remove(EventPayload.TOOL)
                if EventPayload.FUNCTION_OUTPUT in payload:
                    span.log(
                        kind=Kind.Tool,
                        content=ToolResultContent(
                            tool_call_id=tool_call_id,
                            tool_result=payload[EventPayload.FUNCTION_OUTPUT],
                            status="success",
                            extra=None,
                        ),
                    )
                    unhandled_payloads.remove(EventPayload.FUNCTION_OUTPUT)

                # For all other fields, we will log them as SYSTEM events.
                Callback._handle_unknown_payload(
                    span, {key: value for key, value in payload.items() if key in unhandled_payloads}, **annotations
                )

            case _:
                logger.debug("Unknown event type encounter '%s'. Recording as SYSTEM.", event_type)
                span.log(kind=Kind.System, content=payload)

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: typing.Optional[dict[str, typing.Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: typing.Any,
    ) -> str:
        trace: Callback.TraceNode = self.active_traces[-1]

        annotations = dict()
        if parent_id != "":
            annotations["parent_id"] = parent_id
        if event_id != "":
            annotations["event_id"] = event_id

        trace.children[event_type] = trace.span.new(name=event_type, **annotations)
        trace.children[event_type].enter()
        self._handle_payload(trace.children[event_type], event_type, payload)
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: typing.Optional[dict[str, typing.Any]] = None,
        event_id: str = "",
        **kwargs: typing.Any,
    ) -> None:
        span: Span = self.active_traces[-1].children[event_type]
        self._handle_payload(span, event_type, payload)
        span.exit()

    def start_trace(self, trace_id: typing.Optional[str] = None) -> None:
        new_span = self.root_span.new(name="start_trace", trace_id=trace_id)
        self.active_traces += [
            Callback.TraceNode(
                span=new_span,
                children=dict(),
            )
        ]
        new_span.enter()

    def end_trace(
        self,
        trace_id: typing.Optional[str] = None,
        trace_map: typing.Optional[dict[str, typing.List[str]]] = None,
    ) -> None:
        trace = self.active_traces.pop()
        trace.span.exit()
