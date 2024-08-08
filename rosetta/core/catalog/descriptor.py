import pydantic
import typing

from ..record.descriptor import RecordDescriptor


class CatalogDescriptor(pydantic.BaseModel):
    """ This model represents a persistable tool catalog,
        especially for local and/or in-memory representations.
    """

    catalog_schema_version: str

    kind: str = None

    embedding_model: str

    # For git, this is a git repo commit SHA / HASH, which
    # records the repo commit when the 'rosetta index' was run.
    # Ex: "g11aa22bb".
    repo_commit_id: str

    source_dirs: typing.Union[list[str] | None] = None

    # TODO: Besides the repo_commit_id for the HEAD, we might also
    # want to track all the tags and/or branches which point to the
    # HEAD's repo_commit_id? That way, users might be able to perform
    # catalog search/find()'s based on a given tag (e.g., "v1.17.0").

    items: list[RecordDescriptor]
