import langchain_core.messages
import langchain_core.runnables
import langgraph.prebuilt
import typing

from agentc_core.activity import Span
from agentc_core.activity.models.content import ToolResultContent


class ToolNode(langgraph.prebuilt.ToolNode):
    def __init__(self, span: Span, *args, **kwargs):
        self.span = span
        super().__init__(*args, **kwargs)

    def _run_one(
        self,
        call: langchain_core.messages.ToolCall,
        input_type: typing.Literal["list", "dict", "tool_calls"],
        config: langchain_core.runnables.RunnableConfig,
    ) -> langchain_core.messages.ToolMessage:
        result = super(ToolNode, self)._run_one(call, input_type, config)
        self.span.log(
            content=ToolResultContent(
                tool_call_id=result.tool_call_id, tool_result=result.content, status=result.status
            )
        )
        return result

    async def _arun_one(
        self,
        call: langchain_core.messages.ToolCall,
        input_type: typing.Literal["list", "dict", "tool_calls"],
        config: langchain_core.runnables.RunnableConfig,
    ) -> langchain_core.messages.ToolMessage:
        result = await super(ToolNode, self)._arun_one(call, input_type, config)
        self.span.log(
            content=ToolResultContent(
                tool_call_id=result.tool_call_id, tool_result=result.content, status=result.status
            )
        )
        return result
