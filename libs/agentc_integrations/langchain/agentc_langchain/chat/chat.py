import dataclasses
import logging
import typing
import typing_extensions
import uuid

from agentc_core.activity import Span
from agentc_core.analytics import Kind
from agentc_core.analytics.content import ToolCallContent
from agentc_core.analytics.content import ToolResultContent
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.load.dump import default
from langchain_core.messages import AIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.messages import BaseMessage
from langchain_core.messages import FunctionMessage
from langchain_core.messages import FunctionMessageChunk
from langchain_core.messages import HumanMessage
from langchain_core.messages import HumanMessageChunk
from langchain_core.messages import SystemMessage
from langchain_core.messages import SystemMessageChunk
from langchain_core.messages import ToolMessage
from langchain_core.messages import ToolMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.outputs import ChatResult
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

_TYPE_TO_KIND_MAPPING = {
    HumanMessage.__name__: Kind.Human,
    HumanMessageChunk.__name__: Kind.Human,
    AIMessage.__name__: Kind.LLM,
    AIMessageChunk.__name__: Kind.LLM,
    SystemMessage.__name__: Kind.System,
    SystemMessageChunk.__name__: Kind.System,
    ToolMessage.__name__: Kind.Tool,
    ToolMessageChunk.__name__: Kind.Tool,
    FunctionMessage.__name__: Kind.Tool,
    FunctionMessageChunk.__name__: Kind.Tool,
}


def _determine_kind_from_type(message: BaseMessage) -> Kind:
    message_type_name = type(message).__name__
    if message_type_name in _TYPE_TO_KIND_MAPPING:
        return _TYPE_TO_KIND_MAPPING[message_type_name]
    else:
        logger.debug(f'Unknown message type encountered: {message.type}. Tagging as "system".')
        return Kind.System


def _content_from_message(message: BaseMessage) -> typing.Iterable[typing.Any]:
    match _determine_kind_from_type(message):
        case Kind.Tool:
            tool_message: ToolMessage = message
            yield ToolResultContent(
                tool_call_id=tool_message.tool_call_id,
                tool_result=tool_message.content,
                status=tool_message.status,
                extra=default(message),
            )
        case Kind.LLM:
            ai_message: AIMessage = message
            if ai_message.content is not None and ai_message.content != "":
                yield ai_message.content
            for tool_call in ai_message.tool_calls:
                yield ToolCallContent(
                    tool_name=tool_call["name"],
                    tool_args=tool_call["args"],
                    tool_call_id=tool_call["id"],
                    status="success",
                    extra=default(message),
                )
            for invalid_tool_call in ai_message.invalid_tool_calls:
                yield ToolCallContent(
                    tool_name=invalid_tool_call["name"],
                    tool_args=invalid_tool_call["args"],
                    tool_call_id=invalid_tool_call["id"],
                    status="error",
                    extra=default(message),
                )
        case _:
            yield message.content


def _model_from_message(message: BaseMessage, chat_model: BaseChatModel) -> dict | None:
    if isinstance(message, AIMessage):
        if message.response_metadata is not None:
            return message.response_metadata.get("model_name", None)
        else:
            return chat_model
    return None


def _accept_messages(messages: typing.List[BaseMessage], span: Span, **kwargs) -> None:
    for message in messages:
        for content in _content_from_message(message):
            with span.new(name=message.type) as content_span:
                content_span.log(kind=_determine_kind_from_type(message), content=content, **kwargs)


class Callback(BaseCallbackHandler):
    """A callback that will log all LLM calls using the given span as the root."""

    @dataclasses.dataclass
    class LeafNode:
        span: Span
        model: dict | None = None

    @dataclasses.dataclass
    class InternalNode:
        span: Span
        children: dict[uuid.UUID, "Callback.LeafNode"]

    def Node(self, run_id: uuid.UUID, parent_run_id: typing.Optional[uuid.UUID] = None) -> LeafNode:
        # First, our parent span...
        if parent_run_id is None:
            parent_run_id = "_"
        if parent_run_id not in self.node_map:
            self.node_map[parent_run_id] = Callback.InternalNode(
                span=self.root_span.new(name=str(parent_run_id)), children=dict()
            )
        internal_node: Callback.InternalNode = self.node_map[parent_run_id]

        # ...now, our child span.
        if run_id not in internal_node.children:
            internal_node.children[run_id] = Callback.LeafNode(span=internal_node.span.new(name=str(run_id)))
        return internal_node.children[run_id]

    def __init__(self, span: Span):
        self.node_map: dict[uuid.UUID | typing.Literal["_"], Callback.InternalNode] = dict()
        self.root_span = span
        super().__init__()

    def on_chat_model_start(
        self,
        serialized: dict[str, typing.Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: uuid.UUID,
        parent_run_id: typing.Optional[uuid.UUID] = None,
        tags: typing.Optional[list[str]] = None,
        metadata: typing.Optional[dict[str, typing.Any]] = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        node = self.Node(run_id, parent_run_id)
        node.model = serialized
        node.span.enter()
        for message_set in messages:
            _accept_messages(message_set, node.span)
        return super().on_chat_model_start(
            serialized, messages, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        parent_run_id: typing.Optional[uuid.UUID] = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        node = self.Node(run_id, parent_run_id)
        for generation_set in response.generations:
            logger.debug(f"LLM has returned the message: {generation_set}")
            for generation in generation_set:
                node.span.log(kind=Kind.LLM, content=generation.message.text(), model_name=node.model)
        node.span.exit()
        return super().on_llm_end(response, run_id=run_id, parent_run_id=parent_run_id, **kwargs)


@typing_extensions.deprecated(
    "agentc_langchain.chat.audit has been deprecated. " "Please use agentc_langchain.chat.Callback instead."
)
def audit(chat_model: BaseChatModel, span: Span) -> BaseChatModel:
    """A method to (dynamically) dispatch the :py:meth:`BaseChatModel._generate` and :py:meth:`BaseChatModel._stream`
    methods (as well as their asynchronous variants :py:meth:`BaseChatModel._agenerate` and
    :py:meth:`BaseChatModel._astream`) to methods that log LLM calls.

    :param chat_model: The LangChain chat model to audit.
    :param span: The Agent Catalog Span to bind to the chat model messages.
    :return: The same LangChain chat model that was passed in, but with methods dispatched to audit LLM calls.
    """
    generate_dispatch = chat_model._generate
    agenerate_dispatch = chat_model._agenerate
    stream_dispatch = chat_model._stream
    astream_dispatch = chat_model._astream

    def _generate(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> ChatResult:
        results = generate_dispatch(messages, stop, run_manager, **kwargs)
        for result in results.generations:
            logger.debug(f"LLM has returned the message: {result}")
            with span.new(name="_generate") as generation:
                _accept_messages(messages, generation)
                generation.log(
                    kind=Kind.LLM,
                    content=_content_from_message(result.message),
                    model_name=_model_from_message(result.message, chat_model),
                )

        return results

    def _stream(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> typing.Iterator[ChatGenerationChunk]:
        iterator = stream_dispatch(messages, stop, run_manager, **kwargs)

        # For sanity at analytics-time, we'll aggregate the chunks here.
        result_chunk: ChatGenerationChunk = None
        for chunk in iterator:
            logger.debug(f"LLM has returned the chunk: {chunk}")
            if result_chunk is None:
                result_chunk = chunk
            else:
                result_chunk += chunk
            yield chunk

        # We have exhausted our iterator. Log the resultant chunk.
        with span.new(name="_stream") as generation:
            _accept_messages(messages, generation)
            generation.log(
                kind=Kind.LLM,
                content=_content_from_message(result_chunk.message),
                model_name=_model_from_message(result_chunk.message, chat_model),
            )

    async def _agenerate(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ):
        results = await agenerate_dispatch(messages, stop, run_manager, **kwargs)
        for result in results.generations:
            logger.debug(f"LLM has returned the message: {result}")
            with span.new(name="_agenerate") as generation:
                _accept_messages(messages, generation)
                generation.log(
                    kind=Kind.LLM,
                    content=_content_from_message(result.message),
                    model_name=_model_from_message(result.message, chat_model),
                )

        return results

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: typing.Optional[list[str]] = None,
        run_manager: typing.Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> typing.AsyncIterator[ChatGenerationChunk]:
        iterator = astream_dispatch(messages, stop, run_manager, **kwargs)

        # For sanity at analytics-time, we'll aggregate the chunks here.
        result_chunk: ChatGenerationChunk = None
        async for chunk in iterator:
            logger.debug(f"LLM has returned the chunk: {chunk}")
            if result_chunk is None:
                result_chunk = chunk
            else:
                result_chunk += chunk
            yield chunk

        # We have exhausted our iterator. Log the resultant chunk.
        with span.new(name="_astream") as generation:
            _accept_messages(messages, generation)
            generation.log(
                kind=Kind.LLM,
                content=_content_from_message(result_chunk.message),
                model_name=_model_from_message(result_chunk.message, chat_model),
            )

    # Note: Pydantic fiddles around with __setattr__, so we need to skirt around this.
    object.__setattr__(chat_model, "_generate", _generate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_stream", _stream.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_agenerate", _agenerate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_astream", _astream.__get__(chat_model, BaseChatModel))
    return chat_model
