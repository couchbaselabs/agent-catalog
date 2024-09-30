import logging
import rosetta_core.activity.auditor.base
import rosetta_core.analytics.log
import typing
import uuid

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

logger = logging.getLogger(__name__)


_TYPE_TO_KIND_MAPPING = {
    HumanMessage.__name__: rosetta_core.analytics.Kind.Human,
    HumanMessageChunk.__name__: rosetta_core.analytics.Kind.Human,
    AIMessage.__name__: rosetta_core.analytics.Kind.LLM,
    AIMessageChunk.__name__: rosetta_core.analytics.Kind.LLM,
    SystemMessage.__name__: rosetta_core.analytics.Kind.System,
    SystemMessageChunk.__name__: rosetta_core.analytics.Kind.System,
    ToolMessage.__name__: rosetta_core.analytics.Kind.Tool,
    ToolMessageChunk.__name__: rosetta_core.analytics.Kind.Tool,
    FunctionMessage.__name__: rosetta_core.analytics.Kind.Tool,
    FunctionMessageChunk.__name__: rosetta_core.analytics.Kind.Tool,
}


def _determine_kind_from_type(message: BaseMessage) -> rosetta_core.analytics.Kind:
    message_type_name = type(message).__name__
    if message_type_name in _TYPE_TO_KIND_MAPPING:
        return _TYPE_TO_KIND_MAPPING[message_type_name]
    else:
        logger.debug(f'Unknown message type encountered: {message.type}. Tagging as "system".')
        return rosetta_core.analytics.Kind.System


def _content_from_message(message: BaseMessage) -> dict[str, typing.Any]:
    content_dict = {"dump": default(message)}
    if message.content != "":
        content_dict["content"] = message.content

    # If we have tool calls, extract them.
    message_type_name = type(message).__name__
    if message_type_name == AIMessage.__name__ or message_type_name == AIMessageChunk.__name__:
        ai_message: AIMessage = message
        if len(ai_message.tool_calls) > 0:
            content_dict["tool_calls"] = "\n".join(f"{x['name']}({x['args']})" for x in ai_message.tool_calls)
        if len(ai_message.invalid_tool_calls) > 0:
            content_dict["invalid_tool_calls"] = "\n".join(
                f"{x['name']}({x['args']})" for x in ai_message.invalid_tool_calls
            )
    return content_dict


def _accept_messages(
    messages: typing.List[BaseMessage], auditor: rosetta_core.activity.auditor.base.AuditorType, **kwargs
) -> None:
    for message in messages:
        auditor.accept(kind=_determine_kind_from_type(message), content=_content_from_message(message), **kwargs)


def audit(
    chat_model: BaseChatModel,
    session: typing.AnyStr,
    auditor: rosetta_core.activity.auditor.base.AuditorType,
) -> BaseChatModel:
    """A method to (dynamically) dispatch the '_generate' & '_stream' methods to methods that log LLM calls."""
    # TODO (GLENN): We should capture the _agenerate and _astream methods as well.
    generate_dispatch = chat_model._generate
    stream_dispatch = chat_model._stream

    def _generate(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> ChatResult:
        grouping_id = uuid.uuid4().hex
        _accept_messages(messages, auditor, session=session, grouping=grouping_id)
        results = generate_dispatch(messages, stop, run_manager, **kwargs)
        for result in results.generations:
            logger.debug(f"LLM has returned the message: {result}")
            auditor.accept(
                kind=rosetta_core.analytics.Kind.LLM,
                content=_content_from_message(result.message),
                session=session,
                grouping=grouping_id,
            )
        return results

    def _stream(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> typing.Iterator[ChatGenerationChunk]:
        grouping_id = uuid.uuid4().hex
        _accept_messages(messages, auditor, session=session, grouping=grouping_id)
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
        auditor.accept(
            kind=rosetta_core.analytics.Kind.LLM,
            content=_content_from_message(result_chunk.message),
            session=session,
            grouping=grouping_id,
        )

    # Note: Pydantic fiddles around with __setattr__, so we need to skirt around this.
    object.__setattr__(chat_model, "_generate", _generate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_stream", _stream.__get__(chat_model, BaseChatModel))
    return chat_model
