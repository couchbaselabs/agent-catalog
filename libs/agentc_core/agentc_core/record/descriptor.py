import enum
import jsbeautifier
import json
import pathlib
import pydantic
import typing

from ..version import VersionDescriptor
from ..version.identifier import VersionSystem

BEAUTIFY_OPTS = jsbeautifier.BeautifierOptions(
    options={
        "indent_size": 2,
        "indent_char": " ",
        "max_preserve_newlines": -1,
        "preserve_newlines": False,
        "keep_array_indentation": False,
        "brace_style": "expand",
        "unescape_strings": False,
        "end_with_newline": False,
        "wrap_line_length": 0,
        "comma_first": False,
        "indent_empty_lines": False,
    }
)


class RecordKind(enum.StrEnum):
    PythonFunction = "python_function"
    SQLPPQuery = "sqlpp_query"
    SemanticSearch = "semantic_search"
    HTTPRequest = "http_request"
    Prompt = "prompt"


class RecordDescriptor(pydantic.BaseModel):
    """This model represents a tool's persistable description or metadata."""

    model_config = pydantic.ConfigDict(validate_assignment=True, use_enum_values=True, extra="allow")

    record_kind: typing.Literal[
        RecordKind.PythonFunction,
        RecordKind.SQLPPQuery,
        RecordKind.SemanticSearch,
        RecordKind.HTTPRequest,
        RecordKind.Prompt,
    ] = pydantic.Field(description="The type of catalog entry (python tool, prompt, etc...).")

    name: str = pydantic.Field(
        description="A short (Python-identifier-valid) name for the tool, where multiple versions of the "
        "same tool would have the same name.",
        examples=["get_current_stock_price"],
    )

    description: str = pydantic.Field(
        description="Text used to describe an entry's purpose. "
        "For a *.py tool, this is the python function's docstring. "
    )

    # TODO: One day also track source line numbers?
    source: pathlib.Path = pydantic.Field(
        description="Source location of the file, relative to where index was called.",
        examples=[pathlib.Path("src/tools/finance.py")],
    )

    version: VersionDescriptor = pydantic.Field(
        description="A low water-mark that defines the earliest version this record is valid under.",
    )

    embedding: typing.Optional[list[float]] = pydantic.Field(
        default_factory=list, description="Embedding used to search for the record."
    )

    annotations: typing.Optional[dict[str, str] | None] = pydantic.Field(
        default=None,
        description="Dictionary of user-defined annotations attached to this record.",
        examples=[{"gdpr_2016_compliant": '"false"', "ccpa_2019_compliant": '"true"'}],
    )

    @pydantic.computed_field
    @property
    def identifier(self) -> str:
        suffix = self.version.identifier or ""
        if self.version.is_dirty:
            suffix += "_dirty"
        match self.version.version_system:
            case VersionSystem.Git:
                suffix = "git_" + suffix

        return f"{self.source}:{self.name}:{suffix}"

    @identifier.setter
    def identifier(self, identifier: str) -> str:
        # This is purely a computed field, we do not need to set anything else.
        pass

    def __str__(self):
        # Note: this method should only be used to display info (use model_dump to persist this record).
        return jsbeautifier.beautify(
            json.dumps(
                self.model_dump(exclude={"embedding"}, exclude_none=True, exclude_unset=True, mode="json"),
                sort_keys=True,
            ),
            opts=BEAUTIFY_OPTS,
        )

    def __hash__(self):
        return hash(self.identifier)
