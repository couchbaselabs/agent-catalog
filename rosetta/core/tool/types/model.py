import dataclasses
import pathlib
import pydantic
import openapi_parser
import logging
import typing
import abc
import enum
import json
import yaml
import re

from .kind import ToolKind

logger = logging.getLogger(__name__)


class _Metadata(abc.ABC, pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra='forbid',
        use_enum_values=True
    )

    @staticmethod
    def _check_if_valid_json_schema(input_dict: str):
        # TODO (GLENN): We should be checking more than just if the value can be directly serialized to JSON.
        json.loads(input_dict)


class SQLPPQueryMetadata(_Metadata):
    name: str
    description: str
    input: str

    # TODO (GLENN): Infer our output in the future by first running the query.
    output: str

    # We will only parse SQL++ query front-matter in a .sqlpp file, so this field is optional.
    tool_kind: ToolKind = ToolKind.SQLPPQuery

    @staticmethod
    def read_front_matter(sqlpp_file: pathlib.Path) -> dict:
        with sqlpp_file.open('r') as fp:
            matches = re.findall(r'/\*(.*)\*/', fp.read(), re.DOTALL)
            if len(matches) == 0:
                raise ValueError(f'Malformed input! No multiline comment found for {sqlpp_file}.')
            elif len(matches) != 1:
                logger.warning('More than one multi-line comment found. Using first comment.')
            return yaml.safe_load(matches[0])

    @pydantic.field_validator('input', 'output')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: str):
        cls._check_if_valid_json_schema(v)
        return v

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_sqlpp_query(cls, v: ToolKind):
        if v != ToolKind.SQLPPQuery:
            raise ValueError('Cannot create instance of SQLPPQueryMetadata w/ non SQLPPQuery class!')
        return v

    @pydantic.field_validator('name')
    @classmethod
    def name_should_be_valid_identifier(cls, v: str):
        if not v.isidentifier():
            raise ValueError(f'name {v} is not a valid identifier!')
        return v


class SemanticSearchMetadata(_Metadata):
    class VectorSearchMetadata(pydantic.BaseModel):
        # TODO (GLENN): Copy all vector-search-specific validations here.
        bucket: str
        scope: str
        collection: str
        index: str
        vector_field: str
        text_field: str
        embedding_model: str
        num_candidates: int = 3

    name: str
    description: str
    input: str
    vector_search: VectorSearchMetadata
    tool_kind: ToolKind

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_semantic_search(cls, v: ToolKind):
        if v != ToolKind.SemanticSearch:
            raise ValueError('Cannot create instance of SemanticSearchMetadata w/ non SemanticSearch class!')
        return v

    @pydantic.field_validator('input')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: str):
        cls._check_if_valid_json_schema(v)
        return v

    @pydantic.field_validator('input')
    @classmethod
    def value_should_be_non_empty(cls, v: str):
        input_dict = json.loads(v)
        if len(input_dict) == 0:
            raise ValueError('SemanticSearch cannot have an empty input!')
        return v

    @pydantic.field_validator('name')
    @classmethod
    def name_should_be_valid_identifier(cls, v: str):
        if not v.isidentifier():
            raise ValueError(f'name {v} is not a valid identifier!')
        return v


class HTTPRequestMetadata(_Metadata):
    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, openapi_parser.parser.Schema):
                result_dict = dict()
                for k, v in dataclasses.asdict(obj).items():
                    result_dict[k] = self.default(v)
                return result_dict

            elif isinstance(obj, openapi_parser.parser.Property):
                return {
                    'name': obj.name,
                    'schema': self.default(obj.schema)
                }

            elif isinstance(obj, enum.Enum):
                return obj.value

            else:
                return obj

    class OpenAPIMetadata(pydantic.BaseModel):
        filename: typing.Optional[str] = None
        url: typing.Optional[str] = None

        class OperationMetadata(pydantic.BaseModel):
            path: str
            method: str

            # These are set by our parent class.
            _specification: openapi_parser.parser.Operation
            _servers: list[openapi_parser.parser.Server]
            _parent_parameters: list[openapi_parser.parser.Parameter] = list()

            @property
            def parameters(self) -> list[openapi_parser.parser.Parameter]:
                if len(self._specification.parameters) == 0:
                    return self._parent_parameters
                else:
                    return self._specification.parameters

            @property
            def specification(self) -> openapi_parser.parser.Operation:
                return self._specification

            @property
            def servers(self) -> list[openapi_parser.parser.Server]:
                return self._servers

            def __str__(self):
                return f'{self.method} {self.path}'

        operations: list[OperationMetadata]
        _open_api_spec: openapi_parser.parser.Specification

        @pydantic.model_validator(mode='after')
        def operations_must_be_valid(self) -> typing.Self:
            # We need the filename or the URL. Also, both cannot exist at the same time.
            if self.filename is None and self.url is None:
                raise ValueError('Either filename or url must be specified.')
            if self.filename is not None and self.url is not None:
                raise ValueError('Both filename and url cannot be specified at the same time.')

            # We should be able to access the specification file here (validation is done internally here).
            self._open_api_spec = openapi_parser.parse(self.filename or self.url)
            if len(self._open_api_spec.servers) > 0:
                servers = self._open_api_spec.servers
            elif self.filename is not None:
                servers = [
                    openapi_parser.parser.Server(url='https://localhost/'),
                    openapi_parser.parser.Server(url='http://localhost/')
                ]
            else:  # self.url is not None
                servers = [openapi_parser.parser.Server(self.url)]

            # Check the operation path...
            for operation in self.operations:
                specification_path = None
                for p in self._open_api_spec.paths:
                    if operation.path == p.url:
                        specification_path = p
                        break
                if specification_path is None:
                    raise ValueError(f'Operation {operation} does not exist in the spec.')

                # ...and then the method.
                specification_operation = None
                for m in specification_path.operations:
                    if operation.method.lower() == m.method.value.lower():
                        specification_operation = m
                        break
                if specification_operation is None:
                    raise ValueError(f'Operation {operation} does not exist in the spec.')

                # We additionally impose that a description and an operationId must exist.
                if specification_operation.description is None:
                    raise ValueError(f'Description must be specified for operation {operation}.')
                if specification_operation.operation_id is None:
                    raise ValueError(f'OperationId must be specified for operation {operation}.')

                # TODO (GLENN): openapi_parser doesn't support the option to specify operation servers (OpenAPI 3.1.0).
                operation._servers = servers
                operation._specification = specification_operation
                if specification_path.parameters is not None:
                    operation._parent_parameters = specification_path.parameters
            return self

    open_api: OpenAPIMetadata
    tool_kind: ToolKind

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_http_request(cls, v: ToolKind):
        if v != ToolKind.HTTPRequest:
            raise ValueError('Cannot create instance of HTTPRequestMetadata w/ non HTTPRequest class!')
        return v
