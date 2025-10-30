import enum
import jsbeautifier
import json
import pydantic
import typing

from ..prompt.models import PromptDescriptor
from ..record.descriptor import BEAUTIFY_OPTS
from ..tool.descriptor.models import HTTPRequestToolDescriptor
from ..tool.descriptor.models import PythonToolDescriptor
from ..tool.descriptor.models import SemanticSearchToolDescriptor
from ..tool.descriptor.models import SQLPPQueryToolDescriptor
from ..version import VersionDescriptor
from agentc_core.learned.model import EmbeddingModel


class CatalogKind(enum.StrEnum):
    Tool = "tool"
    Prompt = "prompt"


RecordDescriptorUnionType = typing.Annotated[
    PythonToolDescriptor
    | SQLPPQueryToolDescriptor
    | SemanticSearchToolDescriptor
    | HTTPRequestToolDescriptor
    | PromptDescriptor,
    pydantic.Discriminator("record_kind"),
]


class CatalogDescriptor(pydantic.BaseModel):
    """This model represents a persistable tool/prompt catalog for local and in-memory catalog representations."""

    model_config = pydantic.ConfigDict(use_enum_values=True)

    schema_version: str = pydantic.Field(
        description="The version of the catalog schema. This field is used across agentc SDK versions."
    )

    library_version: str = pydantic.Field(
        description="The version of the agentc SDK library that last wrote the catalog data."
    )

    kind: CatalogKind = pydantic.Field(description="The type of items within the catalog.")

    embedding_model: EmbeddingModel = pydantic.Field(
        description="Embedding model used for tool/prompt descriptions within the catalog.",
    )

    version: VersionDescriptor = pydantic.Field(
        description="A unique identifier that defines a catalog version / snapshot / commit.",
    )

    source_dirs: list[str] = pydantic.Field(
        description="A list of source directories that were crawled to generate this catalog."
    )

    items: list[RecordDescriptorUnionType] = pydantic.Field(description="The entries in the catalog.")

    def __str__(self):
        return jsbeautifier.beautify(
            json.dumps(
                self.model_dump(
                    # TODO (GLENN): Should we be excluding null-valued fields here?
                    exclude_none=True,
                    exclude_unset=True,
                    mode="json",
                ),
                sort_keys=True,
            ),
            opts=BEAUTIFY_OPTS,
        )
