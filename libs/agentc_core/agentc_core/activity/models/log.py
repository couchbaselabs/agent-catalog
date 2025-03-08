import pydantic
import typing
import uuid

from ..models.content import Content
from agentc_core.version import VersionDescriptor


class Log(pydantic.BaseModel):
    class Span(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(use_enum_values=True, frozen=True)

        session: str = pydantic.Field(
            description="The 'session' (a runtime identifier) that this span is associated with.",
            default_factory=lambda: uuid.uuid4().hex,
        )

        name: list[str] = pydantic.Field(
            description="The name of the span. This is a list of names that represent the span hierarchy.",
            examples=[["my_application", "my_agent", "my_task"], ["my_application", "my_agent"]],
        )

    model_config = pydantic.ConfigDict(use_enum_values=True, frozen=True)

    identifier: str = pydantic.Field(
        description="A unique identifier for this record. This field is typically a UUID.",
        default_factory=lambda: uuid.uuid4().hex,
    )

    span: "Log.Span" = pydantic.Field(
        description="The span (i.e., a list of names and a session ID) that this record is associated with."
    )

    timestamp: pydantic.AwareDatetime = pydantic.Field(
        description="Timestamp of the generated record. This field must have a timezone attached as well.",
        examples=["2024-08-26T12:02:59.500Z", "2024-08-26T12:02:59.500+00:00"],
    )

    content: Content = pydantic.Field(
        description="The content of the record. This should be as close to the producer as possible.",
        discriminator="kind",
    )

    annotations: typing.Optional[typing.Dict] = pydantic.Field(
        description="Additional annotations that can be added to the message.", default_factory=dict
    )

    catalog_version: VersionDescriptor = pydantic.Field(
        description="A unique identifier that defines a catalog version / snapshot / commit."
    )
