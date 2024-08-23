import enum
import pydantic
import typing

from ..version import VersionDescriptor


class Role(enum.StrEnum):
    Human = "human"
    Tool = "tool"
    Assistant = "assistant"
    Feedback = "feedback"


class Message(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True, frozen=True)

    role: Role = pydantic.Field(
        description="The type of producer of this message.",
        examples=[Role.Human, Role.Tool, Role.Assistant, Role.Feedback],
    )

    content: typing.AnyStr = pydantic.Field(
        description="The content of the message. Ideally, this content is captured immediately before / after "
        "the LLM call itself."
    )

    model: typing.AnyStr = pydantic.Field(description="The specific model (LLM) that this message is associated with.")

    catalog_version: VersionDescriptor = pydantic.Field(
        description="A unique identifier that defines a catalog version / snapshot / commit."
    )
