import enum
import pydantic
import typing


class VersionSystem(enum.StrEnum):
    Git = "git"
    Raw = "raw"


class VersionDescriptor(pydantic.BaseModel):
    identifier: typing.Optional[str] = pydantic.Field(
        description="A unique identifier that defines a catalog snapshot / version / commit. "
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
        description="The kind of versioning system used with this \"snapshot\".",
        default=VersionSystem.Git
    )
    metadata: typing.Optional[dict[str, str]] = pydantic.Field(
        description="A set of system-defined annotations that are used to identify records. "
                    "This field should NOT be saved on published, and will only exist in the catalog. ",
        default_factory=None,
    )

    @pydantic.model_validator(mode='after')
    def non_dirty_must_have_identifier(self) -> typing.Self:
        if self.identifier is None and not self.is_dirty:
            raise ValueError('A non-dirty version descriptor cannot have an empty identifier!')
        return self
