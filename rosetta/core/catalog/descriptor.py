import pydantic
import typing
import enum

from ..tool.descriptor.models import (
    SemanticSearchToolDescriptor,
    SQLPPQueryToolDescriptor,
    HTTPRequestToolDescriptor,
    PythonToolDescriptor
)

# Special value for repo_commit_id that means
# the repo or a file is dirty / untracked.
REPO_DIRTY = "_DIRTY_"


class CatalogKind(enum.StrEnum):
    Tool = 'tool'
    Prompt = 'prompt'

    # TODO (GLENN): Include other classes.


class CatalogDescriptor(pydantic.BaseModel):
    """ This model represents a persistable tool catalog,  especially for local and/or in-memory representations. """

    catalog_schema_version: str

    kind: CatalogKind

    embedding_model: str

    # For git, this is a git repo commit SHA / HASH, which
    # records the repo's commit id when 'rosetta index' was run.
    # Ex: "g11aa234" or REPO_DIRTY.
    repo_commit_id: str

    source_dirs: list[str]

    items: list[typing.Annotated[
        typing.Union[
            SemanticSearchToolDescriptor,
            SQLPPQueryToolDescriptor,
            HTTPRequestToolDescriptor,
            PythonToolDescriptor
        ],
        pydantic.Field(discriminator="record_kind")
    ]]
