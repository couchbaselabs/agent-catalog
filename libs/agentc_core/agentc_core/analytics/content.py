import typing


class TransitionContent(typing.TypedDict):
    to_state: typing.Optional[typing.Any]
    from_state: typing.Optional[typing.Any]
    extra: typing.Optional[typing.Any]


class CustomContent(typing.TypedDict):
    name: str
    value: typing.Any
    extra: typing.Optional[typing.Any]


class ToolCallContent(typing.TypedDict):
    tool_name: str
    tool_args: typing.Dict[str, typing.Any]
    tool_call_id: str
    status: typing.Optional[typing.Literal["success", "error"]]
    extra: typing.Optional[typing.Any]


class ToolResultContent(typing.TypedDict):
    tool_call_id: str
    tool_result: typing.Any
    status: typing.Optional[typing.Literal["success", "error"]]
    extra: typing.Optional[typing.Any]
