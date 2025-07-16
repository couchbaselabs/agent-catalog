import langchain_core.messages
import langchain_core.runnables
import langchain_core.tools
import langgraph.prebuilt
import typing

from agentc_core.activity import Span
from agentc_core.activity.models.content import ToolResultContent


class ToolNode(langgraph.prebuilt.ToolNode):
    """A tool node that logs tool results to a span.

    .. card:: Class Description

        This class will record the results of each tool invocation to the span that is passed to it (ultimately
        generating :py:class:`ToolResultContent` log entries).
        This class does *not* log tool calls (i.e., :py:class:`ToolCallContent` log entries) as these are typically
        logged with :py:class:`ChatCompletionContent` log entries.

        Below, we illustrate a minimal working example of how to use this class with
        :py:class:`agentc_langchain.chat.Callback` to record :py:class:`ChatCompletionContent` log entries,
        :py:class:`ToolCallContent` log entries, and :py:class:`ToolResultContent` log entries.

        .. code-block:: python

            import langchain_openai
            import langchain_core.tools
            import langgraph.prebuilt
            import agentc_langchain.chat
            import agentc_langgraph
            import agentc

            # Create a span to bind to the chat model messages.
            catalog = agentc.Catalog()
            root_span = catalog.Span(name="root_span")

            # Create a chat model.
            chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", callbacks=[])

            # Create a callback with the appropriate span, and attach it to the chat model.
            my_agent_span = root_span.new(name="my_agent")
            callback = agentc_langchain.chat.Callback(span=my_agent_span)
            chat_model.callbacks.append(callback)

            # Grab the correct tools and output from the catalog.
            my_agent_prompt = catalog.find("prompt", name="my_agent")
            my_agent_tools = agentc_langgraph.tool.ToolNode(
                span=my_agent_span,
                tools=[
                    langchain_core.tools.tool(
                        tool.func,
                        args_schema=tool.input,
                    ) for tool in my_agent_prompt.tools
                ]
            )
            my_agent_output = my_agent_prompt.output

            # Finally, build your agent.
            my_agent = langgraph.prebuilt.create_react_agent(
                model=chat_model,
                tools=my_agent_tools,
                prompt=my_agent_prompt,
                response_format=my_agent_output
            )

    .. note::

        For all constructor parameters, see the documentation for :py:class:`langgraph.prebuilt.ToolNode`
        `here <https://langchain-ai.github.io/langgraph/reference/prebuilt/#langgraph.prebuilt.tool_node.ToolNode>`__.

    """

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
