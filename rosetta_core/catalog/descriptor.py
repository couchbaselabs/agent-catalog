import enum
import jsbeautifier
import json
import pydantic
import typing

from ..record.descriptor import BEAUTIFY_OPTS
from ..tool.descriptor import ToolDescriptorUnionType
from ..version import VersionDescriptor


class CatalogKind(enum.StrEnum):
    Tool = "tool"
    Prompt = "prompt"

    # TODO (GLENN): Include other classes.


class CatalogDescriptor(pydantic.BaseModel):
    """This model represents a persistable tool catalog,  especially for local and/or in-memory representations."""

    model_config = pydantic.ConfigDict(use_enum_values=True)

    catalog_schema_version: str = pydantic.Field(
        description="The version of the catalog schema. This field is used across rosetta SDK versions."
    )

    kind: CatalogKind = pydantic.Field(description="The type of items within the catalog.")

    embedding_model: str = pydantic.Field(
        description="The sentence-transformers embedding model used to generate the vector representations "
        "of each catalog entry.",
        examples=["sentence-transformers/all-MiniLM-L12-v2"],
    )

    version: VersionDescriptor = pydantic.Field(
        description="A unique identifier that defines a catalog version / snapshot / commit.",
    )

    source_dirs: list[str] = pydantic.Field(
        description="A list of source directories that were crawled to generate this catalog."
    )

    project: typing.Optional[str] = pydantic.Field(
        description="An optional user-defined field to group snapshots by.",
        default="main",  # TODO (GLENN): Should we use a different name here?
    )

    items: list[ToolDescriptorUnionType] = pydantic.Field(description="The entries in the catalog.")

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
