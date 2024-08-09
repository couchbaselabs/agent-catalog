import pydantic
import pathlib
import typing
import json

from .kind import RecordKind


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, RecordKind):
            return o.value
        elif isinstance(o, pathlib.Path):
            return str(o.absolute())
        else:
            return super(JsonEncoder, self).default(o)


class RecordDescriptor(pydantic.BaseModel):
    """ This model represents a tool's persistable description or metadata. """

    # A fully qualified unique identifier for the tool.
    # Ex: "src/tools/finance.py:get_current_stock_price:g11223344".
    identifier: str

    # The type of catalog entry (python tool, prompt, etc...).
    kind: RecordKind

    # A short name for the tool, where multiple versions
    # of the same tool would have the same name.
    # Ex: "get_current_stock_price".
    name: str

    # For a *.py tool, this is the python function's docstring.
    description: str

    # Ex: "src/tools/finance.py".
    # TODO: One day also track source line numbers?
    source: pathlib.Path

    # For git, this is a git commit SHA / HASH.
    # Ex: "g11223344".
    repo_commit_id: str = None

    # Embedding used to search this record.
    embedding: list[float]

    # TODO (GLENN): Do we need this?
    content: typing.Optional[str] = None

    @property
    def pretty_json(self) -> str:
        # TODO (GLENN): Leverage the built in Pydantic JSON serialization?
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
