import pydantic
import typing
import pathlib
import enum


class ToolKind(str, enum.Enum):
    PythonFunction = 'python_function'
    SQLPPQuery = 'sqlpp_query'
    SemanticSearch = 'semantic_search'

    def __str__(self):
        return self.value


class ToolDescriptor(pydantic.BaseModel):
    """ This model represents a tool catalog entry. """
    identifier: pydantic.UUID4

    name: str
    description: str
    embedding: typing.List[float]

    source: pathlib.Path
    kind: ToolKind
