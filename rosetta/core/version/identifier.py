import enum
import pydantic
import typing


class VersionSystem(enum.StrEnum):
    Git = "git"
    Raw = "raw"


class SnapshotDescriptor(pydantic.BaseModel):
    identifier: typing.Optional[str] = pydantic.Field(
        description="A unique identifier that defines a catalog snapshot. "
                    "For git, this is the git repo commit SHA / HASH.",
        examples=["g11223344"],
        default=None
    )
    is_dirty: typing.Optional[bool] = pydantic.Field(
        description="True if the item being described is 'dirty' (i.e., has diverged from the file "
                    "captured with its identifier.).",
        default=False
    )
    version_system: VersionSystem = pydantic.Field(
        description="The kind of versioning system used with this snapshot.",
        default=VersionSystem.Git
    )
    annotations: typing.Optional[dict[str, str]] = pydantic.Field(
        description="A set of optional annotations that are used to additionally identify records.",
        default_factory=dict,
    )

    @pydantic.model_validator(mode='after')
    def non_dirty_must_have_identifier(self) -> typing.Self:
        if self.identifier is None and not self.is_dirty:
            raise ValueError('A non-dirty snapshot descriptor cannot have an empty identifier!')
        return self
