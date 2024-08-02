import typing
import pydantic
import enum


class MessageType(enum.StrEnum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"
    TOOL = "tool"


class Message(pydantic.BaseModel):
    role: MessageType
    content: str


class History(pydantic.BaseModel):
    messages: typing.Optional[list[Message]] = list()

    def __iadd__(self, new_message: Message):
        self.messages.append(new_message)
        return self

    def __iter__(self):
        yield from self.messages
