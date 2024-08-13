import pydantic
import pathlib
import enum
import typing
import json


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, RecordKind):
            return o.value
        elif isinstance(o, pathlib.Path):
            return str(o.absolute())
        else:
            return super(JsonEncoder, self).default(o)


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

    # TODO (GLENN): Maybe this should be a computed property?
    identifier: str = pydantic.Field(
        description="A fully qualified unique identifier for the tool.",
        examples=["src/tools/finance.py:get_current_stock_price:g11223344"]
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
        # TODO (GLENN): Is this description accurate?
        description="Source location of the file, relative to where index was called.",
        examples=['src/tools/finance.py']
    )

    repo_commit_id: str = pydantic.Field(
        description="A unique identifier that attaches a record to a catalog snapshot. "
                    "For git, this is the git repo commit SHA / HASH.",
        examples=['g11223344', '_DIRTY_']
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

    def __str__(self) -> str:
        # TODO (GLENN): Leverage the built-in Pydantic JSON serialization?
        descriptor_as_dict = self.dict()
        descriptor_as_dict['embedding'] = \
            descriptor_as_dict['embedding'][0:3] \
            + ['...']
        return json.dumps(
            descriptor_as_dict,
            sort_keys=True,
            indent=4,
            cls=JsonEncoder
        )

    def __hash__(self):
        return hash(self.identifier)
