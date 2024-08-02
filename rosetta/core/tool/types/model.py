import types

import pydantic
import openapi_parser
import typing
import abc
import json

from .kind import ToolKind


class _Metadata(abc.ABC, pydantic.BaseModel):
    @staticmethod
    def _check_if_valid_json_schema(input_dict: dict):
        # TODO (GLENN): We should be checking more than just if the value can be directly serialized to JSON.
        json.dumps(input_dict)


class SQLPPQueryMetadata(_Metadata):
    name: str
    description: str
    input: dict

    # TODO (GLENN): Infer our output in the future by first running the query.
    output: dict

    # We will only parse SQL++ query front-matter in a .sqlpp file, so this field is optional.
    tool_kind: typing.Optional[ToolKind] = ToolKind.SQLPPQuery

    @pydantic.field_validator('input', 'output')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: dict):
        cls._check_if_valid_json_schema(v)

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_sqlpp_query(cls, v: ToolKind):
        if v != ToolKind.SQLPPQuery:
            raise ValueError('Cannot create instance of SQLPPQueryMetadata w/ non SQLPPQuery class!')


class SemanticSearchMetadata(_Metadata):
    class VectorSearchMetadata(pydantic.BaseModel):
        bucket: str
        scope: str
        collection: str
        index: str
        vector_field: str
        text_field: str
        embedding_model: str
        num_candidates: int = 3

    tool_kind: ToolKind
    name: str
    description: str
    input: dict
    vector_search: VectorSearchMetadata

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_semantic_search(cls, v: ToolKind):
        if v != ToolKind.SemanticSearch:
            raise ValueError('Cannot create instance of SemanticSearchMetadata w/ non SemanticSearch class!')

    @pydantic.field_validator('input')
    @classmethod
    def value_should_be_valid_json_schema(cls, v: dict):
        cls._check_if_valid_json_schema(v)


class HTTPRequestMetadata(_Metadata):
    class OpenAPIMetadata(pydantic.BaseModel):
        class OperationMetadata(pydantic.BaseModel):
            path: str
            method: str

            # These are set by our parent class.
            _specification: openapi_parser.parser.Operation
            _parameter_schemas: list[openapi_parser.parser.Schema] = list()
            _parameter_names: list[str] = list()
            _servers: list[openapi_parser.parser.Server]

            @property
            def operation_id(self) -> str:
                return self._specification.operation_id

            @property
            def description(self) -> str:
                return self._specification.description

            @property
            def parameters(self) -> dict:
                # TODO (GLENN): I'm pretty sure that openapi_parser handles $ref, but we should double check.
                output_dict = dict()
                for name, schema in zip(self._parameter_names, self._parameter_schemas):
                    output_dict[name] = schema
                return output_dict

            @property
            def responses(self) -> list[openapi_parser.parser.Response]:
                return self._specification.responses

            @property
            def servers(self) -> list[str]:
                return self._servers

            def __str__(self):
                return f'{self.method} {self.path}'

        filename: typing.Optional[str] = None
        url: typing.Optional[str] = None
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
                    if operation.method == m.method:
                        specification_operation = m
                        break
                if specification_operation is None:
                    raise ValueError(f'Operation {operation} does not exist in the spec.')

                # We additionally impose that a description and an operationId must exist.
                if specification_operation.description is None:
                    raise ValueError(f'Description must be specified for operation {operation}.')
                if specification_operation.operation_id is None:
                    raise ValueError(f'OperationId must be specified for operation {operation}.')

                # Set fields required for model generation.
                operation._specification = specification_operation
                if specification_operation.parameters is None and specification_path.parameters is not None:
                    operation._parameters = specification_path.parameters
                else:
                    operation._parameters = specification_operation.parameters

                # TODO (GLENN): openapi_parser doesn't support the option to specify operation servers (OpenAPI 3.1.0).
                operation._servers = servers

    tool_kind: ToolKind
    open_api: OpenAPIMetadata

    @pydantic.field_validator('tool_kind')
    @classmethod
    def tool_kind_should_be_http_request(cls, v: ToolKind):
        if v != ToolKind.HTTPRequest:
            raise ValueError('Cannot create instance of HTTPRequestMetadata w/ non HTTPRequest class!')
