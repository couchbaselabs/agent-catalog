import pydantic
import pathlib

from ..tool import types

from ..tool.types.descriptor import ToolDescriptor as CoreToolDescriptor


class CatalogDescriptor(pydantic.BaseModel):
    """ This model represents a persistable tool catalog,
        especially for local and/or in-memory representations.
    """

    catalog_schema_version: str

    # For git, this is a git repo commit SHA / HASH, which
    # records the repo commit when the 'rosetta index' was run.
    # Ex: "g11aa22bb".
    repo_commit_id: str

    items: list[CoreToolDescriptor]


class ToolDescriptor(pydantic.BaseModel):
    """ This model represents a tool catalog entry.

        !!! OBSOLETED !!! MOVED: TODO: This will be deleted once the indexing
        related refactoring is completed. This has been replaced/moved to
        rosetta.core.tool.types.descriptor.ToolDescriptor.
    """

    identifier: str

    name: str
    description: str
    embedding: list[float]

    source: pathlib.Path
    kind: types.ToolKind
