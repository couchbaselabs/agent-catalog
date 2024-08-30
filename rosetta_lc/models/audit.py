import logging
import rosetta.auditor
import typing

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
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


def _determine_role_from_type(message: BaseMessage) -> rosetta.auditor.Role:
    match type(message).__name__:
        case HumanMessage.__name__ | HumanMessageChunk.__name__:
            return rosetta.auditor.Role.Human
        case AIMessage.__name__ | AIMessageChunk.__name__:
            return rosetta.auditor.Role.Assistant
        case SystemMessage.__name__ | SystemMessageChunk.__name__:
            return rosetta.auditor.Role.System
        case (
            ToolMessage.__name__
            | ToolMessageChunk.__name__
            | FunctionMessage.__name__
            | FunctionMessageChunk.__name__
        ):
            return rosetta.auditor.Role.Tool
        case _:
            logger.debug(f'Unknown message type encountered: {message.type}. Tagging as "system".')
            return rosetta.auditor.Role.System


def audit(chat_model: BaseChatModel, auditor: rosetta.Auditor = None) -> BaseChatModel:
    """A method to (dynamically) dispatch the '_generate' & '_stream' methods to methods that log LLM calls."""
    if auditor is None:
        # TODO (GLENN): Pull the LLM name from somewhere else (e.g., we aren't capturing gpt-4o).
        auditor = rosetta.auditor.Auditor(llm_name=chat_model._llm_type)

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
        for message in messages:
            auditor.accept(_determine_role_from_type(message), message.content)
        results = generate_dispatch(messages, stop, run_manager, **kwargs)
        for result in results.generations:
            logger.debug(f"LLM has returned the message: {result}")
            auditor.accept(rosetta.auditor.Role.Assistant, result.message.content)
        return results

    def _stream(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> typing.Iterator[ChatGenerationChunk]:
        for message in messages:
            auditor.accept(_determine_role_from_type(message), message.content)
        iterator = stream_dispatch(messages, stop, run_manager, **kwargs)

        # For sanity at analytics-time, we'll aggregate the chunks here.
        result_text = ""
        for chunk in iterator:
            logger.debug(f"LLM has returned the chunk: {chunk}")
            result_text += chunk.text
            yield chunk

        # We have exhausted our iterator. Log the resultant chunk.
        auditor.accept(rosetta.auditor.Role.Assistant, result_text)

    # Note: Pydantic fiddles around with __setattr__, so we need to skirt around this.
    object.__setattr__(chat_model, "_generate", _generate.__get__(chat_model, BaseChatModel))
    object.__setattr__(chat_model, "_stream", _stream.__get__(chat_model, BaseChatModel))
    return chat_model
