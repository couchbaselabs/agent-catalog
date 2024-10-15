import typing


class TransitionContent(typing.TypedDict):
    to_state: typing.Optional[str]
    from_state: typing.Optional[str]
    extra: typing.Optional[typing.Any]
