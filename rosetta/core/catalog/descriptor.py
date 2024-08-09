import pydantic
import typing

from ..record.descriptor import RecordDescriptor


 # Special value for repo_commit_id that means
 # the repo or a file is dirty / untracked.
REPO_DIRTY = "_DIRTY_"


class CatalogDescriptor(pydantic.BaseModel):
    """ This model represents a persistable tool catalog,
        especially for local and/or in-memory representations.
    """

    catalog_schema_version: str

    kind: str = None

    embedding_model: str

    # For git, this is a git repo commit SHA / HASH, which
    # records the repo commit when the 'rosetta index' was run.
    # Ex: "g11aa234".
    repo_commit_id: str

    source_dirs: typing.Union[list[str] | None] = None

    items: list[RecordDescriptor]
