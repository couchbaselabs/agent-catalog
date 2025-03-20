import abc
import agentc_core.learned.model
import dataclasses
import enum
import inspect
import json
import logging
import openapi_parser
import pathlib
import pydantic
import re
import typing
import yaml

from ...record.descriptor import RecordDescriptor
from ...record.descriptor import RecordKind
from ...record.helper import JSONSchemaValidatingMixin
from ...security import import_module
from ...version import VersionDescriptor
from ..decorator import get_annotations
from ..decorator import get_description
from ..decorator import get_name
from ..decorator import is_tool
from .secrets import CouchbaseSecrets
from .secrets import EmbeddingModelSecrets

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
    class PythonContent(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(frozen=True)

        file_content: str
        func_content: str
        line_no_start: int
        line_no_end: int

    record_kind: typing.Literal[RecordKind.PythonFunction]
    content: "PythonToolDescriptor.PythonContent"

    class Factory(_BaseFactory):
        def __iter__(self) -> typing.Iterable["PythonToolDescriptor"]:
            imported_module = import_module(self.filename)
            with open(self.filename, "r") as fp:
                source_contents = fp.read()
            for _, tool in inspect.getmembers(imported_module):
                if not is_tool(tool):
                    continue

                source_lines, start_line = inspect.getsourcelines(tool)
                logger.debug("Found Python tool '%s' at line %d.", get_name(tool), start_line)
                if get_description(tool) is None:
                    raise ValueError(
                        f"Description must be specified for tool {get_name(tool)}! "
                        f"Please give this tool a docstring."
                    )
                record_descriptor = PythonToolDescriptor(
                    record_kind=RecordKind.PythonFunction,
                    name=get_name(tool),
                    description=get_description(tool),
                    source=self.filename,
                    content=PythonToolDescriptor.PythonContent(
                        file_content=source_contents,
                        func_content="".join(source_lines),
                        line_no_start=start_line,
                        line_no_end=start_line + len(source_lines) - 1,
                    ),
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
    input: dict
    query: str
    output: typing.Optional[dict] = None
    secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
    record_kind: typing.Literal[RecordKind.SQLPPQuery]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            # Below, we enumerate all fields that appear in a .sqlpp file.
            name: str
            description: str
            input: str | dict
            output: typing.Optional[str | dict] = None
            secrets: list[CouchbaseSecrets] = pydantic.Field(min_length=1, max_length=1)
            record_kind: typing.Optional[typing.Literal[RecordKind.SQLPPQuery] | None] = None
            annotations: typing.Optional[dict[str, str] | None] = None

            @pydantic.field_validator("input", "output")
            @classmethod
            def _value_should_be_valid_json_schema(cls, v: str | dict):
                if v is not None and isinstance(v, str):
                    v = cls.check_if_valid_json_schema_str(v)
                elif v is not None and isinstance(v, dict):
                    v = cls.check_if_valid_json_schema_dict(v)
                else:
                    raise ValueError("Type must be either a string or a YAML dictionary.")
                return v

            @pydantic.field_validator("name")
            @classmethod
            def _name_should_be_valid_identifier(cls, v: str):
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
        bucket: str
        scope: str
        collection: str
        index: str
        vector_field: str
        text_field: str
        embedding_model: agentc_core.learned.model.EmbeddingModel
        num_candidates: int = 3

    input: dict
    vector_search: VectorSearchMetadata
    secrets: list[CouchbaseSecrets | EmbeddingModelSecrets] = pydantic.Field(min_length=1, max_length=2)
    record_kind: typing.Literal[RecordKind.SemanticSearch]

    class Factory(_BaseFactory):
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            # Below, we enumerate all fields that appear in a .yaml file for semantic search.
            record_kind: typing.Literal[RecordKind.SemanticSearch]
            name: str
            description: str
            input: str | dict
            secrets: list[CouchbaseSecrets | EmbeddingModelSecrets] = pydantic.Field(min_length=1, max_length=2)
            annotations: typing.Optional[dict[str, str] | None] = None
            vector_search: "SemanticSearchToolDescriptor.VectorSearchMetadata"
            num_candidates: typing.Optional[pydantic.PositiveInt] = 3

            @pydantic.field_validator("input")
            @classmethod
            def _value_should_be_valid_json_schema(cls, v: str | dict):
                if v is not None and isinstance(v, str):
                    v = cls.check_if_valid_json_schema_str(v)
                elif v is not None and isinstance(v, dict):
                    v = cls.check_if_valid_json_schema_dict(v)
                else:
                    raise ValueError("Type must be either a string or a YAML dictionary.")
                return v

            @pydantic.field_validator("input")
            @classmethod
            def _value_should_be_non_empty(cls, v: dict):
                if len(v) == 0:
                    raise ValueError("SemanticSearch cannot have an empty input!")
                return v

            @pydantic.field_validator("name")
            @classmethod
            def _name_should_be_valid_identifier(cls, v: str):
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

    class SpecificationMetadata(pydantic.BaseModel):
        filename: typing.Optional[pathlib.Path | None] = None
        url: typing.Optional[pathlib.Path | None] = None

    class OperationHandle:
        def __init__(
            self,
            path: str,
            method: str,
            operation: openapi_parser.parser.Operation,
            servers: list[openapi_parser.parser.Server],
            parent_parameters: list[openapi_parser.parser.Parameter] = None,
        ):
            self.path = path
            self.method = method
            self.servers = servers
            self._operation = operation
            self._parent_parameters = parent_parameters

        @property
        def parameters(self) -> list[openapi_parser.parser.Parameter]:
            if len(self._operation.parameters) == 0:
                return self._parent_parameters
            else:
                return self._operation.parameters

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
            open_api_spec = openapi_parser.parse(spec_filename.absolute().as_uri(), strict_enum=False)
        else:
            open_api_spec = openapi_parser.parse(url, strict_enum=False)

        # Determine our servers.
        if len(open_api_spec.servers) > 0:
            servers = open_api_spec.servers
        elif spec_filename is not None:
            servers = [
                openapi_parser.parser.Server(url="https://localhost/"),
                openapi_parser.parser.Server(url="http://localhost/"),
            ]
        else:  # url is not None
            servers = [openapi_parser.parser.Server(url)]

        # Check the operation path...
        specification_path = None
        for p in open_api_spec.paths:
            if operation.path == p.url:
                specification_path = p
                break
        if specification_path is None:
            raise ValueError(f"Operation {operation} does not exist in the spec.")

        # ...and then the method.
        specification_operation = None
        for m in specification_path.operations:
            if operation.method.lower() == m.method.value.lower():
                specification_operation = m
                break
        if specification_operation is None:
            raise ValueError(f"Operation {operation} does not exist in the spec.")

        # We additionally impose that a description and an operationId must exist.
        if specification_operation.description is None:
            raise ValueError(f"Description must be specified for operation {operation}.")
        if specification_operation.operation_id is None:
            raise ValueError(f"OperationId must be specified for operation {operation}.")

        # TODO (GLENN): openapi_parser doesn't support operation servers (OpenAPI 3.1.0).
        return HTTPRequestToolDescriptor.OperationHandle(
            method=operation.method,
            path=operation.path,
            servers=servers,
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

    class JSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, openapi_parser.parser.Schema):
                result_dict = dict()
                for k, v in dataclasses.asdict(obj).items():
                    result_dict[k] = self.default(v)
                return result_dict

            elif isinstance(obj, openapi_parser.parser.Property):
                return {"name": obj.name, "schema": self.default(obj.schema)}

            elif isinstance(obj, enum.Enum):
                return obj.value

            else:
                return obj

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
