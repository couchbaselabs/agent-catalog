import pydantic
import pathlib

from .kind import ToolKind


class ToolDescriptor(pydantic.BaseModel):
    """ This model represents a tool's persistable description or metadata. """

    # A fully qualified unique identifier for the tool.
    # Ex: "src/tools/finance.py:get_current_stock_price:g11223344".
    identifier: str

    # A short name for the tool, where multiple versions
    # of the same tool would have the same name.
    # Ex: "get_current_stock_price".
    name: str

    kind: ToolKind

    # For a *.py tool, this is the python function's docstring.
    description: str

    # Ex: "src/tools/finance.py".
    # TODO: One day also track source line numbers?
    source: pathlib.Path

    # For git, this is a git commit SHA / HASH.
    # Ex: "g11223344".
    repo_commit_id: str

    embedding: list[float]
