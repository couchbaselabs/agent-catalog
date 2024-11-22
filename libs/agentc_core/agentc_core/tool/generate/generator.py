import abc
import dataclasses
import datamodel_code_generator
import datetime
import jinja2
import json
import logging
import openapi_pydantic
import openapi_schema_to_json_schema
import pathlib
import pydantic
import typing

from ...record.descriptor import RecordDescriptor
from ..descriptor import HTTPRequestToolDescriptor
from ..descriptor import SemanticSearchToolDescriptor
from ..descriptor import SQLPPQueryToolDescriptor
from .common import INPUT_MODEL_CLASS_NAME_IN_TEMPLATES
from .common import OUTPUT_MODEL_CLASS_NAME_IN_TEMPLATES
from .common import GeneratedCode
from .common import generate_model_from_json_schema

logger = logging.getLogger(__name__)

ModelType = datamodel_code_generator.DataModelType
PythonTarget = datamodel_code_generator.PythonVersion


class _BaseCodeGenerator(pydantic.BaseModel):
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / "templates").resolve(),
        description="Location of the the template files.",
    )

    target_python_version: PythonTarget = pydantic.Field(
        default=PythonTarget.PY_311,
        description="The target Python version for the generated (schema) code.",
    )

    target_model_type: ModelType = pydantic.Field(
        default=ModelType.PydanticV2BaseModel,
        examples=[ModelType.TypingTypedDict, ModelType.PydanticV2BaseModel],
        description="The target model type for the generated (schema) code.",
    )

    @abc.abstractmethod
    def generate(self) -> typing.Iterable[tuple[str, str]]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SQLPPQueryToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SQLPPQueryToolDescriptor:
        return self.record_descriptors[0]

    def generate(self) -> typing.Iterable[str]:
        # Generate a Pydantic model for the input schema...
        input_model = generate_model_from_json_schema(
            json_schema=self.record_descriptor.input,
            class_name=INPUT_MODEL_CLASS_NAME_IN_TEMPLATES,
            python_version=self.target_python_version,
            model_type=self.target_model_type,
        )

        # ...and the output schema.
        output_model = (
            generate_model_from_json_schema(
                json_schema=self.record_descriptor.output,
                class_name=OUTPUT_MODEL_CLASS_NAME_IN_TEMPLATES,
                python_version=self.target_python_version,
                model_type=self.target_model_type,
            )
            if self.record_descriptor.output is not None
            else GeneratedCode(generated_code="", is_list_valued=False, type_name="dict")
        )

        # Instantiate our template.
        with (self.template_directory / "sqlpp_q.jinja").open("r") as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
            rendered_code = template.render(
                {
                    "time": generation_time,
                    "query": self.record_descriptor.query,
                    "tool": self.record_descriptor,
                    "input": input_model,
                    "output": output_model,
                    "secrets": self.record_descriptor.secrets[0].couchbase,
                }
            )
            logger.debug("The following code has been generated:\n" + rendered_code)
            yield rendered_code


class SemanticSearchCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SemanticSearchToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SemanticSearchToolDescriptor:
        return self.record_descriptors[0]

    def generate(self) -> typing.Iterable[str]:
        # Generate a Pydantic model for the input schema.
        input_model = generate_model_from_json_schema(
            json_schema=self.record_descriptor.input,
            class_name=INPUT_MODEL_CLASS_NAME_IN_TEMPLATES,
            python_version=self.target_python_version,
            model_type=self.target_model_type,
        )

        # Instantiate our template.
        with (self.template_directory / "semantic_q.jinja").open("r") as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
            rendered_code = template.render(
                {
                    "time": generation_time,
                    "tool": self.record_descriptor,
                    "input": input_model,
                    "vector_search": self.record_descriptor.vector_search,
                    "secrets": self.record_descriptor.secrets[0].couchbase,
                }
            )
            logger.debug("The following code has been generated:\n" + rendered_code)
            yield rendered_code


class HTTPRequestCodeGenerator(_BaseCodeGenerator):
    body_parameter_collision_handler: typing.Callable[[str], str] = pydantic.Field(default=lambda b: "_" + b)
    record_descriptors: list[HTTPRequestToolDescriptor] = pydantic.Field(min_length=1)

    @dataclasses.dataclass
    class InputContext:
        model: typing.Any
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
            return HTTPRequestCodeGenerator.InputContext(json_schema=base_object, locations_dict=locations, model=None)

    def generate(self) -> typing.Iterable[str]:
        # Iterate over our operations.
        for record_descriptor in self.record_descriptors:
            operation = record_descriptor.handle

            # TODO (GLENN): We should try to build a model for the response (output) in the future.
            # Generate a Pydantic model for the input schema.
            input_context = self._create_json_schema_from_specification(operation)
            if input_context is not None:
                input_context.model = generate_model_from_json_schema(
                    json_schema=json.dumps(input_context.json_schema),
                    class_name=INPUT_MODEL_CLASS_NAME_IN_TEMPLATES,
                    python_version=self.target_python_version,
                    model_type=self.target_model_type,
                )

            # Instantiate our template.
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
                yield rendered_code
