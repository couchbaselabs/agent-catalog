import logging
import typing
import typing_extensions
import uuid

from agentc_core.activity import Span
from agentc_core.activity.models.content import ChatCompletionContent
from agentc_core.activity.models.content import Content
from agentc_core.activity.models.content import RequestHeaderContent
from agentc_core.activity.models.content import SystemContent
from agentc_core.activity.models.content import ToolCallContent
from agentc_core.activity.models.content import ToolResultContent
from agentc_core.activity.models.content import UserContent
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import FunctionMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.outputs import ChatResult
from langchain_core.outputs import LLMResult
from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


def _content_from_message(message: BaseMessage) -> typing.Iterable[Content]:
    match message.type:
        case "ai" | "AIMessageChunk":
            ai_message: AIMessage = message
            yield ChatCompletionContent(output=str(ai_message.content), meta=ai_message.response_metadata)

            for tool_call in ai_message.tool_calls:
                yield ToolCallContent(
                    tool_name=tool_call["name"],
                    tool_args=tool_call["args"],
                    tool_call_id=tool_call["id"],
                    status="success",
                )
            for invalid_tool_call in ai_message.invalid_tool_calls:
                yield ToolCallContent(
                    tool_name=invalid_tool_call["name"],
                    tool_args=invalid_tool_call["args"],
                    tool_call_id=invalid_tool_call["id"],
                    status="error",
                    extra={
                        "error": invalid_tool_call["error"],
                    },
                )

        case "function" | "FunctionMessageChunk":
            function_message: FunctionMessage = message
            yield ToolResultContent(
                tool_result=function_message.content,
                status="success",
            )

        case "tool" | "ToolMessageChunk":
            tool_message: ToolMessage = message
            yield ToolResultContent(
                tool_call_id=tool_message.tool_call_id,
                tool_result=tool_message.content,
                status=tool_message.status,
            )

        case "human" | "HumanMessageChunk":
            human_message: HumanMessage = message
            yield UserContent(value=human_message.content)

        case "system" | "SystemMessageChunk":
            system_message: SystemMessage = message
            yield SystemContent(value=system_message.content, extra={"meta": system_message})

        case _:
            logger.debug("Unknown message type encountered: %s. Logging as System.", message.type)
            base_message: BaseMessage = message
            yield SystemContent(
                value=base_message.content,
                extra={
                    "meta": base_message,
                    "id": base_message.id,
                    "type": message.type,
                },
            )


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
            span.log(content=content, **kwargs)


class Callback(BaseCallbackHandler):
    """A callback that will log all LLM calls using the given span as the root."""

    def __init__(self, span: Span, tools: list[Tool] = None, output: dict = None):
        """
        :param span: The root span to bind to the chat model messages.
        :param tools: The tools that being used by the chat model (i.e., those passed in :py:BaseChatModel.bind_tools).
        :param output: The output type that being used by the chat model (i.e., those passed in
                       :py:BaseChatModel.with_structured_output).
        """
        self.span: Span = span.new(name="agentc_langchain.chat.Callback")
        self.output: dict = output or dict()
        self.tools: list[RequestHeaderContent.Tool] = list()
        if tools is not None:
            for tool in tools:
                self.tools.append(
                    RequestHeaderContent.Tool(name=tool.name, description=tool.description, args_schema=tool.args)
                )

        # The following is set on chat completion.
        self.serialized_model = dict()
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
        self.span.enter()
        self.serialized_model = serialized
        self.span.log(
            RequestHeaderContent(
                tools=self.tools,
                output=self.output,
                meta=serialized,
                extra={
                    "run_id": str(run_id),
                    "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
                    "tags": tags,
                },
            )
        )
        for message_set in messages:
            _accept_messages(message_set, self.span)
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
        for generation_set in response.generations:
            logger.debug(f"LLM has returned the message: {generation_set}")
            for generation in generation_set:
                self.span.log(
                    ChatCompletionContent(
                        output=generation.message.text(),
                        meta=generation.message.response_metadata,
                        extra={"additional_kwargs": generation.message.additional_kwargs},
                    ),
                    run_id=str(run_id),
                    parent_run_id=str(parent_run_id) if parent_run_id is not None else None,
                )
        self.span.exit()
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
                # Each generation gets its own span.
                _accept_messages(messages, generation)
                generation.log(
                    list(_content_from_message(result.message))[0],
                    model=_model_from_message(result.message, chat_model),
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
                content=list(_content_from_message(result_chunk.message))[0],
                model=_model_from_message(result_chunk.message, chat_model),
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
            # Each generation gets its own span.
            logger.debug(f"LLM has returned the message: {result}")
            with span.new(name="_agenerate") as generation:
                _accept_messages(messages, generation)
                generation.log(
                    content=list(_content_from_message(result.message))[0],
                    model=_model_from_message(result.message, chat_model),
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
                content=list(_content_from_message(result_chunk.message))[0],
                model=_model_from_message(result_chunk.message, chat_model),
            )

    # Note: Pydantic fiddles around with __setattr__, so we need to skirt around this.
    object.__setattr__(chat_model, "_generate", _generate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_stream", _stream.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_agenerate", _agenerate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_astream", _astream.__get__(chat_model, BaseChatModel))
    return chat_model
