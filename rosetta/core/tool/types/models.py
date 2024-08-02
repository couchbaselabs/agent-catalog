import pydantic
import typing
import json

from ..descriptor import ToolKind


def _check_if_valid_json_schema(input_dict: typing.Dict):
    # TODO (GLENN): We should be checking more than just if the value can be directly serialized to JSON.
    json.dumps(input_dict)


class SQLPPQueryMetadata(pydantic.BaseModel):
    name: str
    description: str
    input: typing.Dict
    output: typing.Dict

    @pydantic.field_validator('input', 'output')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: typing.Dict):
        _check_if_valid_json_schema(v)


class SemanticSearchMetadata(pydantic.BaseModel):
    class VectorSearch(pydantic.BaseModel):
        bucket: str
        scope: str
        collection: str
        index: str
        vector_field: str
        text_field: str
        embedding_model: str

    tool_class: ToolKind
    name: str
    description: str
    input: typing.Dict
    vector_search: VectorSearch

    @pydantic.field_validator('tool_class')
    @classmethod
    def tool_class_should_be_semantic_search(cls, v: ToolKind):
        if v != ToolKind.SemanticSearch:
            raise ValueError('Cannot create instance of SemanticSearchFrontMatter w/ non SemanticSearch class!')

    @pydantic.field_validator('input')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: typing.Dict):
        _check_if_valid_json_schema(v)


class HTTPRequestMetadata(pydantic.BaseModel):
    class OpenAPI(pydantic.BaseModel):
        file: str


    tool_class: ToolKind


    @pydantic.field_validator('tool_class')
    @classmethod
    def tool_class_should_be_http_request(cls, v: ToolKind):
        if v != ToolKind.SemanticSearch:
            raise ValueError('Cannot create instance of HTTPRequestFrontMatter w/ non HTTPRequest class!')
