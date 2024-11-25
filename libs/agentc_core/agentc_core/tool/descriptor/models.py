import abc
import importlib
import inspect
import json
import logging
import openapi_pydantic
import pathlib
import pydantic
import re
import requests
import sys
import typing
import yaml

from ...record.descriptor import RecordDescriptor
from ...record.descriptor import RecordKind
from ...record.helper import JSONSchemaValidatingMixin
from ...version import VersionDescriptor
from ..decorator import get_annotations
from ..decorator import get_description
from ..decorator import get_name
from ..decorator import is_tool
from .secrets import CouchbaseSecrets

logger = logging.getLogger(__name__)


class _BaseFactory(abc.ABC):
    def __init__(self, filename: pathlib.Path, version: VersionDescriptor):
        """
        :param filename: Name of the file to load the record descriptor from.
        :param version: The version descriptor associated with file describing a set of tools.
        """
        self.filename = filename
        self.version = version

    @abc.abstractmethod
    def __iter__(self):
        pass


class PythonToolDescriptor(RecordDescriptor):
    record_kind: typing.Literal[RecordKind.PythonFunction]
    contents: str

    class Factory(_BaseFactory):
        def __iter__(self) -> typing.Iterable["PythonToolDescriptor"]:
            # Note: this **does not** load the tools themselves into memory.
            # TODO (GLENN): We should avoid blindly putting things in our path.
            if str(self.filename.parent.absolute()) not in sys.path:
                sys.path.append(str(self.filename.parent.absolute()))
            with open(self.filename, "r") as fp:
                source_contents = fp.read()
            imported_module = importlib.import_module(self.filename.stem)
            for _, tool in inspect.getmembers(imported_module):
                if not is_tool(tool):
                    continue
                record_descriptor = PythonToolDescriptor(
                    record_kind=RecordKind.PythonFunction,
                    name=get_name(tool),
                    description=get_description(tool),
                    source=self.filename,
                    contents=source_contents,
                    version=self.version,
                    annotations=get_annotations(tool),
                )
                if record_descriptor.__pydantic_extra__:
                    logger.warning(
                        f"Extra fields found in {self.filename.name} for tool {get_name(tool)}: "
                        f"{record_descriptor.__pydantic_extra__.keys()}. We will ignore these."
                    )
                yield record_descriptor


class SQLPPQueryToolDescriptor(RecordDescriptor):
    input: str
    query: str
    output: typing.Optional[str] = None
    secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
    record_kind: typing.Literal[RecordKind.SQLPPQuery]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            # Below, we enumerate all fields that appear in a .sqlpp file.
            name: str
            description: str
            input: str
            output: typing.Optional[str] = None
            secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
            record_kind: typing.Optional[typing.Literal[RecordKind.SQLPPQuery] | None] = None
            annotations: typing.Optional[dict[str, str] | None] = None

            @pydantic.field_validator("input", "output")
            @classmethod
            def value_should_be_valid_json_schema(cls, v: str):
                if v is not None:
                    cls.check_if_valid_json_schema(v)
                return v

            @pydantic.field_validator("name")
            @classmethod
            def name_should_be_valid_identifier(cls, v: str):
                if not v.isidentifier():
                    raise ValueError(f"name {v} is not a valid identifier!")
                return v

        def __iter__(self) -> typing.Iterable["SQLPPQueryToolDescriptor"]:
            # First, get the front matter from our .sqlpp file.
            with self.filename.open("r") as fp:
                matches = re.findall(r"/\*(.*)\*/", fp.read(), re.DOTALL)
                if len(matches) == 0:
                    raise ValueError(f"Malformed input! No multiline comment found for {self.filename.name}.")
                elif len(matches) != 1:
                    logger.warning("More than one multi-line comment found. Using first comment.")
                metadata = SQLPPQueryToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(matches[0]))
                if metadata.__pydantic_extra__:
                    logger.warning(
                        f"Extra fields found in {self.filename.name}: {metadata.__pydantic_extra__}. "
                        f"We will ignore these."
                    )

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
                query=self.filename.open("r").read(),
                annotations=metadata.annotations,
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
    secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
    record_kind: typing.Literal[RecordKind.SemanticSearch]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            # Below, we enumerate all fields that appear in a .yaml file for semantic search.
            record_kind: typing.Literal[RecordKind.SemanticSearch]
            name: str
            description: str
            input: str
            secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
            annotations: typing.Optional[dict[str, str] | None] = None
            vector_search: "SemanticSearchToolDescriptor.VectorSearchMetadata"
            num_candidates: typing.Optional[pydantic.PositiveInt] = 3

            @pydantic.field_validator("input")
            @classmethod
            def value_should_be_valid_json_schema(cls, v: str):
                cls.check_if_valid_json_schema(v)
                return v

            @pydantic.field_validator("input")
            @classmethod
            def value_should_be_non_empty(cls, v: str):
                input_dict = json.loads(v)
                if len(input_dict) == 0:
                    raise ValueError("SemanticSearch cannot have an empty input!")
                return v

            @pydantic.field_validator("name")
            @classmethod
            def name_should_be_valid_identifier(cls, v: str):
                if not v.isidentifier():
                    raise ValueError(f"name {v} is not a valid identifier!")
                return v

        def __iter__(self) -> typing.Iterable["SemanticSearchToolDescriptor"]:
            with self.filename.open("r") as fp:
                metadata = SemanticSearchToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(fp))
                if metadata.__pydantic_extra__:
                    logger.warning(
                        f"Extra fields found in {self.filename.name}: {metadata.__pydantic_extra__}. "
                        f"We will ignore these."
                    )
                yield SemanticSearchToolDescriptor(
                    record_kind=RecordKind.SemanticSearch,
                    name=metadata.name,
                    description=metadata.description,
                    source=self.filename,
                    version=self.version,
                    secrets=metadata.secrets,
                    input=metadata.input,
                    vector_search=metadata.vector_search,
                    annotations=metadata.annotations,
                )


class HTTPRequestToolDescriptor(RecordDescriptor):
    class OperationMetadata(pydantic.BaseModel):
        path: str
        method: str

        @pydantic.field_validator("method")
        @classmethod
        def method_should_be_valid_http_method(cls, v: str):
            if v.lower() not in {"get", "put", "post", "delete", "options", "head", "patch", "trace"}:
                raise ValueError(f"Invalid HTTP method {v}.")
            return v.upper()

    class SpecificationMetadata(pydantic.BaseModel):
        filename: typing.Optional[pathlib.Path | None] = None
        url: typing.Optional[pathlib.Path | None] = None

    class OperationHandle:
        def __init__(
            self,
            path: str,
            method: str,
            operation: openapi_pydantic.Operation,
            servers: list[openapi_pydantic.Server],
            parent_parameters: list[openapi_pydantic.Parameter] = None,
        ):
            self.path = path
            self.method = method
            self.servers: list[openapi_pydantic.Server] = servers
            self._operation: openapi_pydantic.Operation = operation
            self._parent_parameters: list[openapi_pydantic.Parameter] = parent_parameters

        @property
        def parameters(self) -> list[openapi_pydantic.Parameter]:
            if self._operation.parameters is None or len(self._operation.parameters) == 0:
                return self._parent_parameters
            else:
                return self._operation.parameters

        @property
        def operation_id(self):
            return self._operation.operationId

        @property
        def description(self):
            return self._operation.description

        @property
        def request_body(self):
            return self._operation.requestBody

        def __str__(self):
            return f"{self.method} {self.path}"

    operation: OperationMetadata
    specification: SpecificationMetadata
    record_kind: typing.Literal[RecordKind.HTTPRequest]

    @staticmethod
    def validate_operation(
        source_filename: pathlib.Path | None,
        spec_filename: pathlib.Path | None,
        url: str | None,
        operation: OperationMetadata,
    ):
        # We need the filename or the URL. Also, both cannot exist at the same time.
        if spec_filename is None and url is None:
            raise ValueError("Either filename or url must be specified.")
        if spec_filename is not None and url is not None:
            raise ValueError("Both filename and url cannot be specified at the same time.")

        # We should be able to access the specification file here (validation is done internally here).
        if spec_filename is not None:
            if not spec_filename.exists():
                spec_filename = source_filename.parent / spec_filename
            if not spec_filename.exists():
                raise ValueError(f"Specification file {spec_filename} does not exist.")
            with open(spec_filename, "r") as fp:
                open_api_spec: openapi_pydantic.OpenAPI = openapi_pydantic.OpenAPI.model_validate_json(fp.read())
        else:
            response = requests.get(url)
            if response.status_code != 200:
                raise ValueError(f"Could not fetch OpenAPI specification from {url}.")
            open_api_spec: openapi_pydantic.OpenAPI = openapi_pydantic.OpenAPI.model_validate_json(response.text)

        # Determine our servers.
        if len(open_api_spec.servers) > 0:
            servers = open_api_spec.servers
        elif spec_filename is not None:
            servers = [
                openapi_pydantic.Server(url="https://localhost/"),
                openapi_pydantic.Server(url="http://localhost/"),
            ]
        else:  # url is not None
            servers = [openapi_pydantic.Server(url=url)]

        # Check the operation path...
        specification_path: openapi_pydantic.PathItem = None
        if open_api_spec.paths is None:
            raise ValueError("No paths found in the OpenAPI spec.")
        for k, v in open_api_spec.paths.items():
            if operation.path == k:
                specification_path = v
                break
        if specification_path is None:
            raise ValueError(f"Operation {operation} does not exist in the spec.")

        # ...and then the method.
        match operation.method:
            case "GET":
                specification_operation = specification_path.get
            case "PUT":
                specification_operation = specification_path.put
            case "POST":
                specification_operation = specification_path.post
            case "DELETE":
                specification_operation = specification_path.delete
            case "OPTIONS":
                specification_operation = specification_path.options
            case "HEAD":
                specification_operation = specification_path.head
            case "PATCH":
                specification_operation = specification_path.patch
            case "TRACE":
                specification_operation = specification_path.trace
            case _:
                # We should never reach here (validation should be done by Pydantic earlier).
                raise ValueError(f"Invalid HTTP method {operation.method} found in spec.")
        if specification_operation is None:
            raise ValueError(f"Operation {operation} does not exist in the spec.")

        # We additionally impose that a description and an operationId must exist.
        if specification_operation.description is None:
            raise ValueError(f"Description must be specified for operation {operation}.")
        if specification_operation.operationId is None:
            raise ValueError(f"OperationId must be specified for operation {operation}.")

        return HTTPRequestToolDescriptor.OperationHandle(
            method=operation.method,
            path=operation.path,
            servers=servers + (specification_operation.servers or []),
            operation=specification_operation,
            parent_parameters=specification_path.parameters,
        )

    @property
    def handle(self) -> OperationHandle:
        spec_filename = pathlib.Path(self.specification.filename) if self.specification.filename is not None else None
        return HTTPRequestToolDescriptor.validate_operation(
            source_filename=self.source,
            spec_filename=spec_filename,
            url=self.specification.url,
            operation=self.operation,
        )

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            # Note: we cannot validate this model in isolation (we need the referencing descriptor as well).
            class OpenAPIMetadata(pydantic.BaseModel):
                model_config = pydantic.ConfigDict(extra="allow")
                filename: typing.Optional[str | None] = None
                url: typing.Optional[str | None] = None
                operations: list["HTTPRequestToolDescriptor.OperationMetadata"]

            # Below, we enumerate all fields that appear in a .yaml file for http requests.
            record_kind: typing.Literal[RecordKind.HTTPRequest]
            open_api: OpenAPIMetadata
            annotations: typing.Optional[dict[str, str] | None] = None

        def __iter__(self) -> typing.Iterable["HTTPRequestToolDescriptor"]:
            with self.filename.open("r") as fp:
                metadata = HTTPRequestToolDescriptor.Factory.Metadata.model_validate(yaml.safe_load(fp))
                if metadata.__pydantic_extra__:
                    logger.warning(
                        f"Extra fields found in {self.filename.name}: {metadata.__pydantic_extra__}. "
                        f"We will ignore these."
                    )
                for operation in metadata.open_api.operations:
                    operation_handle = HTTPRequestToolDescriptor.validate_operation(
                        source_filename=self.filename,
                        spec_filename=pathlib.Path(metadata.open_api.filename),
                        url=metadata.open_api.url,
                        operation=operation,
                    )
                    yield HTTPRequestToolDescriptor(
                        record_kind=RecordKind.HTTPRequest,
                        name=operation_handle.operation_id,
                        description=operation_handle.description,
                        source=self.filename,
                        version=self.version,
                        operation=operation,
                        specification=HTTPRequestToolDescriptor.SpecificationMetadata(
                            filename=metadata.open_api.filename, url=metadata.open_api.url
                        ),
                        annotations=metadata.annotations,
                    )
