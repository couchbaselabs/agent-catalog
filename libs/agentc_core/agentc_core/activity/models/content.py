import enum
import logging
import pydantic
import textwrap
import typing

logger = logging.getLogger(__name__)


class Kind(enum.StrEnum):
    """The different types of log content that are recognized."""

    def __new__(cls, value: str, doc: str):
        self = str.__new__(cls, value)
        self._value_ = value
        self.__doc__ = textwrap.dedent(doc)
        return self

    System = (
        "system",
        """
        System refers to messages that are generated by (none other than) the system or application.
        In agent frameworks, these messages are typically templated and instantiated with application-defined
        objectives / instructions.
        """,
    )

    ToolCall = (
        "tool-call",
        """
        ToolCall refers to messages that contain (typically LLM generated) arguments for invoking a tool.
        These logs are not to be confused with *ToolResult* messages which contain the results of invoking a tool.
        """,
    )

    ToolResult = (
        "tool-result",
        """
        ToolResult refers to messages containing the results of invoking a tool.
        These logs are not to be confused with *ToolCall* messages which are (typically) generated by an LLM.
        """,
    )

    ChatCompletion = (
        "chat-completion",
        """
        ChatCompletion refers to messages that are generated using a language model.
        Ideally, these messages should be captured immediately after generation (without any post-processing).
        """,
    )

    RequestHeader = (
        "request-header",
        """
        RequestHeader refers to messages that *specifically* capture tools and output types used in a request to
        a language model.
        """,
    )

    User = (
        "user",
        """
        User refers to messages that are directly sent by (none other than) the user.
        If the application uses prompt templates, these messages refer to the raw user input (not the templated text).
        """,
    )

    Assistant = (
        "assistant",
        """
        Assistant refers to messages that are directly served back to the user.
        These messages exclude any *ModelOutput* or *System* messages that are used internally by the application.
        """,
    )

    Begin = (
        "begin",
        """
        Begin refers to marker messages that are used to indicate the start of a span (e.g., a task, agent, state,
        etc...).
        These messages are typically used to trace the trajectory of a conversation, and are application specific.
        """,
    )

    End = (
        "end",
        """
        End refers to marker messages that are used to indicate the end of a span (e.g., a task, agent, state, etc...).
        These messages are typically used to trace the trajectory of a conversation, and are application specific.
        """,
    )

    KeyValue = (
        "key-value",
        """
        KeyValue refers to messages that contain user-specified data that are to be logged under some span.
        """,
    )


class BaseContent(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True)

    extra: typing.Optional[dict] = pydantic.Field(
        description="Additional data that is associated with the content. This field is optional.", default_factory=dict
    )

    @staticmethod
    def _safe_serialize(obj):
        """Source available at: https://stackoverflow.com/a/74923639"""

        def _safe_serialize_impl(inner_obj):
            if isinstance(inner_obj, list):
                result = list()
                for element in inner_obj:
                    result.append(_safe_serialize_impl(element))
                return result
            elif isinstance(inner_obj, dict):
                result = dict()
                for key, value in inner_obj.items():
                    result[key] = _safe_serialize_impl(value)
                return result
            elif hasattr(inner_obj, "__dict__"):
                if hasattr(inner_obj, "__repr__"):
                    result = inner_obj.__repr__()
                else:
                    # noinspection PyBroadException
                    try:
                        result = inner_obj.__class__.__name__
                    except:
                        result = "object"
                return result
            else:
                return inner_obj

        return _safe_serialize_impl(obj)

    @pydantic.field_serializer("extra", when_used="json")
    def _serialize_extra_if_non_empty(self, extra: dict, _info):
        return self._safe_serialize(extra) if len(extra) > 0 else None


class SystemContent(BaseContent):
    kind: typing.Literal[Kind.System] = Kind.System

    value: str = pydantic.Field(description="The content of the system message.")


class ToolCallContent(BaseContent):
    kind: typing.Literal[Kind.ToolCall] = Kind.ToolCall

    tool_name: str = pydantic.Field(
        description="The name of the tool that is being called. If this tool is indexed with Agent Catalog, this field "
        "should refer to the tool's 'name' field."
    )

    tool_args: dict[str, typing.Any] = pydantic.Field(
        description="The arguments that are going to be passed to the tool. This field should be JSON-serializable."
    )

    tool_call_id: str = pydantic.Field(
        description="The unique identifier associated with a tool call instance. "
        "This field is (typically) parsed from a LLM response and is used to correlate / JOIN this "
        "message with the corresponding ToolResult message."
    )

    status: typing.Optional[typing.Literal["success", "error"]] = "success"

    @pydantic.field_serializer("tool_args", when_used="json")
    def _serialize_tool_args(self, tool_args: dict[str, typing.Any], _info):
        return self._safe_serialize(tool_args)


class ToolResultContent(BaseContent):
    kind: typing.Literal[Kind.ToolResult] = Kind.ToolResult

    tool_call_id: typing.Optional[str] = pydantic.Field(
        description="The unique identifier of the tool call. This field will be used to correlate / JOIN this message "
        "with the corresponding ToolCall message.",
        default=None,
    )

    tool_result: typing.Any = pydantic.Field(
        description="The result of invoking the tool. This field should be JSON-serializable."
    )

    status: typing.Optional[typing.Literal["success", "error"]] = pydantic.Field(
        description="The status of the tool invocation. This field should be one of 'success' or 'error'.",
        default="success",
    )

    @pydantic.field_serializer("tool_result", when_used="json")
    def _serialize_tool_result(self, tool_result: typing.Any, _info):
        return self._safe_serialize(tool_result)


class ChatCompletionContent(BaseContent):
    kind: typing.Literal[Kind.ChatCompletion] = Kind.ChatCompletion

    output: typing.Optional[str] = pydantic.Field(description="The output of the model.", default=None)

    meta: typing.Optional[dict] = pydantic.Field(
        description="The raw response associated with the chat completion. This must be JSON-serializable.",
        default_factory=dict,
    )

    @pydantic.field_serializer("meta", when_used="json")
    def _serialize_meta_if_non_empty(self, meta: dict, _info):
        return self._safe_serialize(meta) if len(meta) > 0 else None


class RequestHeaderContent(BaseContent):
    class Tool(pydantic.BaseModel):
        name: str = pydantic.Field(description="The name of the tool.")
        description: str = pydantic.Field(description="A description of the tool.")
        args_schema: dict = pydantic.Field(description="The (JSON) schema of the tool.")

    kind: typing.Literal[Kind.RequestHeader] = Kind.RequestHeader

    tools: typing.Optional[list[Tool]] = pydantic.Field(
        description="The tools (name, description, schema) included in the request to a model. "
        "For tools indexed by Agent Catalog, this field should refer to the tool's 'name' field. "
        "This field is optional.",
        default=list,
    )

    output: typing.Optional[dict] = pydantic.Field(
        description="The output type of the model (in JSON schema) response. This field is optional.",
        default_factory=dict,
    )

    meta: typing.Optional[dict] = pydantic.Field(
        description="All request parameters associated with the model input. This must be JSON-serializable.",
        default_factory=dict,
    )

    @pydantic.field_serializer("meta", when_used="json")
    def _serialize_meta_if_non_empty(self, meta: dict, _info):
        return self._safe_serialize(meta) if len(meta) > 0 else None


class UserContent(BaseContent):
    kind: typing.Literal[Kind.User] = Kind.User

    value: str = pydantic.Field(description="The captured user input.")

    user_id: typing.Optional[str] = pydantic.Field(
        description="The unique identifier of the user. This field is optional.", default=None
    )


class AssistantContent(BaseContent):
    kind: typing.Literal[Kind.Assistant] = Kind.Assistant

    value: str = pydantic.Field(description="The response served back to the user.")


class BeginContent(BaseContent):
    kind: typing.Literal[Kind.Begin] = Kind.Begin

    state: typing.Optional[typing.Any] = pydantic.Field(
        description="The state logged on entering a span.", default=None
    )


class EndContent(BaseContent):
    kind: typing.Literal[Kind.End] = Kind.End

    state: typing.Optional[typing.Any] = pydantic.Field(description="The state logged on exiting a span.", default=None)


class KeyValueContent(BaseContent):
    kind: typing.Literal[Kind.KeyValue] = Kind.KeyValue

    key: str = pydantic.Field(description="The name of the key-value pair.")

    value: typing.Any = pydantic.Field(
        description="The value of the key-value pair. This value should be JSON-serializable."
    )

    @pydantic.field_serializer("value", when_used="json")
    def _serialize_value(self, value: typing.Any, _info):
        return self._safe_serialize(value)


Content = typing.Union[
    SystemContent,
    ToolCallContent,
    ToolResultContent,
    ChatCompletionContent,
    RequestHeaderContent,
    UserContent,
    AssistantContent,
    BeginContent,
    EndContent,
    KeyValueContent,
]
