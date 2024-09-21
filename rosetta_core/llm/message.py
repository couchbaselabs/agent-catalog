import enum
import pydantic
import typing
import uuid

from ..version import VersionDescriptor


class Role(enum.StrEnum):
    Human = "human"
    System = "system"
    Tool = "tool"
    Assistant = "assistant"
    Feedback = "feedback"


class Message(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(use_enum_values=True, frozen=True)

    timestamp: pydantic.AwareDatetime = pydantic.Field(
        description="Timestamp of the generated message. This field must have a timezone attached as well.",
        examples=["2024-08-26T12:02:59.500Z", "2024-08-26T12:02:59.500+00:00"],
    )

    session: typing.AnyStr = pydantic.Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="The thread / session / conversation this message belongs to.",
    )

    role: Role = pydantic.Field(
        description="The type of producer of this message.",
        examples=[Role.Human, Role.System, Role.Tool, Role.Assistant, Role.Feedback],
    )

    content: typing.Any = pydantic.Field(
        description="The content of the message. This should be as close to the producer as possible.",
    )

    model: typing.AnyStr = pydantic.Field(description="The specific model (LLM) that this message is associated with.")

    grouping: typing.Optional[typing.AnyStr] = pydantic.Field(
        description="A grouping identifier for this message. This is typically associated with a complete "
        "'_generate' invocation.",
        default=None,
    )

    annotations: typing.Optional[typing.Dict] = pydantic.Field(
        description="Additional annotations that can be added to the message.", default_factory=dict
    )

    catalog_version: VersionDescriptor = pydantic.Field(
        description="A unique identifier that defines a catalog version / snapshot / commit."
    )
