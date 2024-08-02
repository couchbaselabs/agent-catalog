import pydantic
import pathlib

from ..tool.types import ToolKind


class ToolDescriptor(pydantic.BaseModel):
    """ This model represents a tool catalog entry. """
    identifier: str

    name: str
    description: str
    embedding: list[float]

    source: pathlib.Path
    kind: ToolKind
