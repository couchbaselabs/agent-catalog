import pydantic
import enum

from ..tool.descriptor import ToolDescriptorUnionType


# Special value for repo_commit_id that means
# the repo or a file is dirty / untracked.
REPO_DIRTY = "_DIRTY_"


class CatalogKind(enum.StrEnum):
    Tool = "tool"
    Prompt = "prompt"
    All = "all"

    # TODO (GLENN): Include other classes.


class CatalogKindModel(pydantic.BaseModel):
    kind: CatalogKind


class CatalogDescriptor(pydantic.BaseModel):
    """This model represents a persistable tool catalog,  especially for local and/or in-memory representations."""

    catalog_schema_version: str = pydantic.Field(
        description="The version of the catalog schema. "
        "This field is used across rosetta SDK versions."
    )

    kind: CatalogKind = pydantic.Field(description="The type of items within the catalog.")

    embedding_model: str = pydantic.Field(
        description="The sentence-transformers embedding model used to generate the vector representations "
        "of each catalog entry.",
        examples=["sentence-transformers/all-MiniLM-L12-v2"],
    )

    snapshot_commit_id: str = pydantic.Field(
        description="A unique identifier that attaches a record to a catalog snapshot. "
        "For git, this is the git repo commit SHA / HASH.",
        examples=["g11223344", REPO_DIRTY],
    )

    source_dirs: list[str] = pydantic.Field(
        description="A list of source directories that were crawled to generate this catalog."
    )

    items: list[ToolDescriptorUnionType] = pydantic.Field(description="The entries in the catalog.")
