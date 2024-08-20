import abc
import dataclasses
import pathlib
import pydantic
import openapi_parser
import logging
import typing
import enum
import json
import sys
import yaml
import re
import importlib
import inspect

from .helper import JSONSchemaValidatingMixin
from .secrets import CouchbaseSecrets
from ..decorator import ToolMarker
from ...version import VersionDescriptor
from ...record.descriptor import (
    RecordKind,
    RecordDescriptor
)

logger = logging.getLogger(__name__)


class _BaseFactory(abc.ABC):
    def __init__(self, filename: pathlib.Path, version: VersionDescriptor):
        """
        :param filename: Name of the file to load the record descriptor from.
        :param version: The version descriptor associated with file describing a set of tools.
        """
        self.filename = filename
        self.version = version


# Note: a Python Tool does not add any additional fields.
class PythonToolDescriptor(RecordDescriptor):
    record_kind: typing.Literal[RecordKind.PythonFunction]

    class Factory(_BaseFactory):
        def __iter__(self) -> typing.Iterable['PythonToolDescriptor']:
            # Note: this **does not** load the tools themselves into memory.
            # TODO (GLENN): We should avoid blindly putting things in our path.
            if not str(self.filename.parent.absolute()) in sys.path:
                sys.path.append(str(self.filename.parent.absolute()))
            imported_module = importlib.import_module(self.filename.stem)
            for name, tool in inspect.getmembers(imported_module):
                if not isinstance(tool, ToolMarker):
                    continue
                yield PythonToolDescriptor(
                    record_kind=RecordKind.PythonFunction,
                    name=name,
                    description=tool.__doc__,
                    source=self.filename,
                    version=self.version,
                    # TODO (GLENN): Add support for user-defined annotations here.
                    annotations=dict()
                )


class SQLPPQueryToolDescriptor(RecordDescriptor):
    input: str
    output: str
    query: str
    secrets: list[CouchbaseSecrets] = pydantic.Field(min_items=1, max_items=1)
    record_kind: typing.Literal[RecordKind.SQLPPQuery]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(
                frozen=True,
                use_enum_values=True
            )

            # Below, we enumerate all fields that appear in a .sqlpp file.
            name: str
            description: str
            input: str
            output: str
            secrets: list[CouchbaseSecrets] = pydantic.Field(min_items=1, max_items=1)
            record_kind: typing.Optional[typing.Literal[RecordKind.SQLPPQuery] | None] = None
            annotations: typing.Optional[dict[str, str] | None] = None

            @pydantic.field_validator('input', 'output')
            @classmethod
            def value_should_be_valid_json_schema(cls, v: str):
                cls.check_if_valid_json_schema(v)
                return v

            @pydantic.field_validator('name')
            @classmethod
            def name_should_be_valid_identifier(cls, v: str):
                if not v.isidentifier():
                    raise ValueError(f'name {v} is not a valid identifier!')
                return v

        def __iter__(self) -> typing.Iterable['SQLPPQueryToolDescriptor']:
            # First, get the front matter from our .sqlpp file.
            with self.filename.open('r') as fp:
                matches = re.findall(r'/\*(.*)\*/', fp.read(), re.DOTALL)
                if len(matches) == 0:
                    raise ValueError(f'Malformed input! No multiline comment found for {self.filename.name}.')
                elif len(matches) != 1:
                    logger.warning('More than one multi-line comment found. Using first comment.')
                metadata = SQLPPQueryToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(matches[0]))

            # Now, generate a single SQL++ tool descriptor.
            yield SQLPPQueryToolDescriptor(
                record_kind=RecordKind.SQLPPQuery,
                name=metadata.name,
                description=metadata.description,
                source=self.filename,
                version=self.version,
                secrets=metadata.secrets,
                input=metadata.input,
                output=metadata.output,
                query=self.filename.open('r').read(),
                annotations=metadata.annotations
            )


class SemanticSearchToolDescriptor(RecordDescriptor):
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

    input: str
    vector_search: VectorSearchMetadata
    secrets: list[CouchbaseSecrets] = pydantic.Field(min_items=1, max_items=1)
    record_kind: typing.Literal[RecordKind.SemanticSearch]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(
                frozen=True,
                use_enum_values=True
            )

            # Below, we enumerate all fields that appear in a .yaml file for semantic search.
            record_kind: typing.Literal[RecordKind.SemanticSearch]
            name: str
            description: str
            input: str
            secrets: list[CouchbaseSecrets] = pydantic.Field(min_items=1, max_items=1)
            annotations: typing.Optional[dict[str, str] | None] = None
            vector_search: 'SemanticSearchToolDescriptor.VectorSearchMetadata'

            @pydantic.field_validator('input')
            @classmethod
            def value_should_be_valid_json_schema(cls, v: str):
                cls.check_if_valid_json_schema(v)
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

        def __iter__(self) -> typing.Iterable['SemanticSearchToolDescriptor']:
            with self.filename.open('r') as fp:
                metadata = SemanticSearchToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(fp))
                yield SemanticSearchToolDescriptor(
                    record_kind=RecordKind.SemanticSearch,
                    name=metadata.name,
                    description=metadata.description,
                    source=self.filename,
                    version=self.version,
                    secrets=metadata.secrets,
                    input=metadata.input,
                    vector_search=metadata.vector_search,
                    annotations=metadata.annotations
                )


class HTTPRequestToolDescriptor(RecordDescriptor):
    class OperationMetadata(pydantic.BaseModel):
        path: str
        method: str

        # These properties are set after validating HTTPRequestToolDescriptor (outer).
        _operation: openapi_parser.parser.Operation
        _servers: list[openapi_parser.parser.Server]
        _parent_parameters: list[openapi_parser.parser.Parameter] = list()

        @property
        def parameters(self) -> list[openapi_parser.parser.Parameter]:
            if len(self._operation.parameters) == 0:
                return self._parent_parameters
            else:
                return self._operation.parameters

        @property
        def servers(self) -> list[openapi_parser.parser.Server]:
            return self._servers

        @property
        def operation_id(self):
            return self._operation.operation_id

        @property
        def description(self):
            return self._operation.description

        @property
        def request_body(self):
            return self._operation.request_body

        def __str__(self):
            return f'{self.method} {self.path}'

    class SpecificationMetadata(pydantic.BaseModel):
        filename: typing.Optional[pathlib.Path | None] = None
        url: typing.Optional[pathlib.Path | None] = None

    operation: OperationMetadata
    specification: SpecificationMetadata
    record_kind: typing.Literal[RecordKind.HTTPRequest]

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

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(
                frozen=True,
                use_enum_values=True
            )

            class OpenAPIMetadata(pydantic.BaseModel):
                filename: typing.Optional[str | None] = None
                url: typing.Optional[str | None] = None
                operations: list['HTTPRequestToolDescriptor.OperationMetadata']

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

                        # TODO (GLENN): openapi_parser doesn't support operation servers (OpenAPI 3.1.0).
                        operation._servers = servers
                        operation._operation = specification_operation
                        if specification_path.parameters is not None:
                            operation._parent_parameters = specification_path.parameters
                    return self

            # Below, we enumerate all fields that appear in a .yaml file for http requests.
            record_kind: typing.Literal[RecordKind.HTTPRequest]
            open_api: OpenAPIMetadata
            annotations: typing.Optional[dict[str, str] | None] = None

        def __iter__(self) -> typing.Iterable['HTTPRequestToolDescriptor']:
            with self.filename.open('r') as fp:
                metadata = HTTPRequestToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(fp))
                for operation in metadata.open_api.operations:
                    yield HTTPRequestToolDescriptor(
                        record_kind=RecordKind.HTTPRequest,
                        name=operation.operation_id,
                        description=operation.description,
                        source=self.filename,
                        version=self.version,
                        operation=operation,
                        specification=HTTPRequestToolDescriptor.SpecificationMetadata(
                            filename=metadata.open_api.filename,
                            url=metadata.open_api.url
                        ),
                        annotations=metadata.annotations
                    )


ToolDescriptorUnionType = typing.Annotated[
    PythonToolDescriptor
    | SQLPPQueryToolDescriptor
    | SemanticSearchToolDescriptor
    | HTTPRequestToolDescriptor,
    pydantic.Field(discriminator='record_kind')
]
