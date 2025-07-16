import abc
import agentc_core.defaults
import dataclasses
import datetime
import jinja2
import json
import logging
import openapi_pydantic
import openapi_schema_to_json_schema
import os
import pathlib
import pydantic
import typing

from ...record.descriptor import RecordDescriptor
from ..descriptor import HTTPRequestToolDescriptor
from ..descriptor import SemanticSearchToolDescriptor
from ..descriptor import SQLPPQueryToolDescriptor
from ..descriptor.secrets import CouchbaseSecrets
from ..descriptor.secrets import EmbeddingModelSecrets

logger = logging.getLogger(__name__)


class GeneratedCode(typing.TypedDict):
    code: str
    args_schema: dict


class _BaseCodeGenerator(pydantic.BaseModel):
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / "templates").resolve(),
        description="Location of the the template files.",
    )

    @abc.abstractmethod
    def generate(self) -> typing.Iterable[GeneratedCode]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SQLPPQueryToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SQLPPQueryToolDescriptor:
        return self.record_descriptors[0]

    def generate(self) -> typing.Iterable[GeneratedCode]:
        # Instantiate our template.
        with (self.template_directory / "sqlpp_q.jinja").open("r") as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
            rendered_code = template.render(
                {
                    "time": generation_time,
                    "query": self.record_descriptor.query,
                    "tool": self.record_descriptor,
                    "secrets": self.record_descriptor.secrets[0].couchbase,
                }
            )
            logger.debug("The following code has been generated:\n" + rendered_code)
            yield GeneratedCode(code=rendered_code, args_schema=self.record_descriptor.input)


class SemanticSearchCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SemanticSearchToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SemanticSearchToolDescriptor:
        return self.record_descriptors[0]

    def generate(self) -> typing.Iterable[GeneratedCode]:
        # Instantiate our template.
        with (self.template_directory / "semantic_q.jinja").open("r") as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read(), autoescape=True)
            generation_time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")

            cluster_secrets = None
            for secret in self.record_descriptor.secrets:
                if isinstance(secret, CouchbaseSecrets):
                    cluster_secrets = secret
                    break
            embedding_secrets = None
            for secret in self.record_descriptor.secrets:
                if isinstance(secret, EmbeddingModelSecrets):
                    embedding_secrets = secret
                    break

            rendered_code = template.render(
                {
                    "time": generation_time,
                    "tool": self.record_descriptor,
                    "vector_search": self.record_descriptor.vector_search,
                    "cluster_secrets": cluster_secrets.couchbase if cluster_secrets is not None else None,
                    "embedding_model": {
                        "secrets": embedding_secrets.embedding if embedding_secrets is not None else None,
                        "cache": os.getenv(
                            "AGENT_CATALOG_SENTENCE_TRANSFORMERS_MODEL_CACHE",
                            agentc_core.defaults.DEFAULT_MODEL_CACHE_FOLDER,
                        ),
                    },
                }
            )
            logger.debug("The following code has been generated:\n" + rendered_code)
            yield GeneratedCode(code=rendered_code, args_schema=self.record_descriptor.input)


class HTTPRequestCodeGenerator(_BaseCodeGenerator):
    body_parameter_collision_handler: typing.Callable[[str], str] = pydantic.Field(default=lambda b: "_" + b)
    record_descriptors: list[HTTPRequestToolDescriptor] = pydantic.Field(min_length=1)

    @dataclasses.dataclass
    class InputContext:
        json_schema: dict
        locations_dict: dict
        content_type: str = openapi_pydantic.DataType.OBJECT

        @property
        def locations(self):
            return f"{json.dumps(self.locations_dict)}"

    @pydantic.field_validator("record_descriptors")
    @classmethod
    def record_descriptors_must_share_the_same_source(cls, v: list[RecordDescriptor]):
        if any(td.source != v[0].source for td in v):
            raise ValueError("Grouped HTTP-Request descriptors must share the same source!")
        return v

    def _create_json_schema_from_specification(self, operation: HTTPRequestToolDescriptor.OperationHandle):
        # Our goal here is to create an easy "interface" for our LLM to call, so we will consolidate parameters
        # and the request body into one model.
        base_object = {"type": "object", "properties": dict()}
        locations = dict()

        # Note: parent parameters are handled in the OperationMetadata class.
        for parameter in operation.parameters:
            base_object["properties"][parameter.name] = openapi_schema_to_json_schema.to_json_schema(
                schema=parameter.param_schema.model_dump(by_alias=True, exclude_none=True)
            )
            locations[parameter.name] = parameter.param_in.lower()

        if operation.request_body is not None:
            json_type_request_content = None
            if "application/json" in operation.request_body.content:
                json_type_request_content = operation.request_body.content["application/json"]

            # TODO (GLENN): Implement other descriptor of request bodies.
            if json_type_request_content is None:
                logger.warning("No application/json content (specification) found in the request body!")
            else:
                from_request_body = openapi_schema_to_json_schema.to_json_schema(
                    schema=dataclasses.asdict(json_type_request_content.schema)
                )
                for k, v in from_request_body.items():
                    # If there are name collisions, we will rename the request body parameter.
                    parameter_name = self.body_parameter_collision_handler(k) if k in base_object["properties"] else k
                    base_object["properties"][parameter_name] = v
                    locations[parameter_name] = "body"

        if len(base_object["properties"]) == 0:
            return None
        else:
            return HTTPRequestCodeGenerator.InputContext(json_schema=base_object, locations_dict=locations)

    def generate(self) -> typing.Iterable[GeneratedCode]:
        # Iterate over our operations.
        for record_descriptor in self.record_descriptors:
            operation = record_descriptor.handle

            # Instantiate our template.
            input_context = self._create_json_schema_from_specification(operation)
            with (self.template_directory / "httpreq_q.jinja").open("r") as tmpl_fp:
                template = jinja2.Template(source=tmpl_fp.read())
                generation_time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
                rendered_code = template.render(
                    {
                        "time": generation_time,
                        "input": input_context,
                        "method": operation.method.upper(),
                        "path": operation.path,
                        "tool": record_descriptor,
                        "urls": [s.url for s in operation.servers],
                    }
                )
                logger.debug("The following code has been generated:\n" + rendered_code)
                yield GeneratedCode(code=rendered_code, args_schema=input_context.json_schema)
