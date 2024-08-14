import pydantic
import pathlib
import enum
import typing

from ..version import SnapshotDescriptor
from ..version.identifier import VersionSystem


class RecordKind(enum.StrEnum):
    PythonFunction = 'python_function'
    SQLPPQuery = 'sqlpp_query'
    SemanticSearch = 'semantic_search'
    HTTPRequest = 'http_request'

    # TODO (GLENN): Include other classes for prompts.
    RawPrompt = 'raw_prompt'
    JinjaPrompt = 'jinja_prompt'


class RecordDescriptor(pydantic.BaseModel):
    """ This model represents a tool's persistable description or metadata. """
    model_config = pydantic.ConfigDict(
        validate_assignment=True,
        use_enum_values=True
    )

    record_kind: typing.Literal[
        RecordKind.PythonFunction,
        RecordKind.SQLPPQuery,
        RecordKind.SemanticSearch,
        RecordKind.HTTPRequest
    ] = pydantic.Field(description="The type of catalog entry (python tool, prompt, etc...).")

    name: str = pydantic.Field(
        description="A short (Python-identifier-valid) name for the tool, where multiple versions of the "
                    "same tool would have the same name.",
        examples=['get_current_stock_price']
    )

    description: str = pydantic.Field(
        description="Text used to describe an entry's purpose. "
                    "For a *.py tool, this is the python function's docstring. "
    )

    # TODO: One day also track source line numbers?
    source: pathlib.Path = pydantic.Field(
        description="Source location of the file, relative to where index was called.",
        examples=[pathlib.Path('src/tools/finance.py')]
    )

    snapshot: SnapshotDescriptor = pydantic.Field(
        description="A low water-mark that defines the earliest snapshot this record belongs to.",
    )

    embedding: typing.Optional[list[float]] = pydantic.Field(
        default_factory=list,
        description="Embedding used to search for the record."
    )

    tags: typing.Optional[list[str] | None] = pydantic.Field(
        default=None,
        description="List of user-defined tags attached to this record.",
        examples=['gdpr_2016_compliant']
    )

    @pydantic.computed_field
    @property
    def identifier(self) -> str:
        suffix = self.snapshot.identifier or ''
        if self.snapshot.is_dirty:
            suffix += '_dirty'
        match self.snapshot.version_system:
            case VersionSystem.Git:
                suffix = 'git_' + suffix

        return f'{self.source}:{self.name}:{suffix}'

    @identifier.setter
    def identifier(self, identifier: str) -> str:
        # This is purely a computed field, we do not need to set anything else.
        pass

    def __hash__(self):
        return hash(self.identifier)
