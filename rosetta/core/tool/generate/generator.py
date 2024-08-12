import datetime
import pathlib
import typing
import uuid
import openapi_parser.parser
import pydantic
import jinja2
import json
import abc
import logging
import dataclasses
import openapi_schema_to_json_schema

from .common import (
    input_model_class_name_in_templates,
    output_model_class_name_in_templates,
    generate_model_from_json_schema,
)
from ..descriptor import (
    SQLPPQueryToolDescriptor,
    SemanticSearchToolDescriptor,
    HTTPRequestToolDescriptor
)
from ...record.descriptor import RecordDescriptor

logger = logging.getLogger(__name__)


class _BaseCodeGenerator(pydantic.BaseModel):
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / 'templates').resolve(),
        description='Location of the the template files.'
    )

    @abc.abstractmethod
    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SQLPPQueryToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SQLPPQueryToolDescriptor:
        return self.record_descriptors[0]

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        # Generate a Pydantic model for the input schema...
        input_model = generate_model_from_json_schema(
            json_schema=self.record_descriptor.input,
            class_name=input_model_class_name_in_templates
        )

        # ...and the output schema.
        output_model = generate_model_from_json_schema(
            json_schema=self.record_descriptor.output,
            class_name=output_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'sqlpp_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'query': self.record_descriptor.query,
                'tool': self.record_descriptor,
                'input': input_model,
                'output': output_model,
                'secrets': self.record_descriptor.secrets[0].couchbase
            })
            logger.debug('The following code has been generated:\n' + rendered_code)

        # ...and write this as a single file to our output directory.
        output_file = output_dir / (uuid.uuid4().hex + '.py')
        with output_file.open('w') as fp:
            fp.write(rendered_code)
            fp.flush()
        return [output_file]


class SemanticSearchCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[SemanticSearchToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    @property
    def record_descriptor(self) -> SemanticSearchToolDescriptor:
        return self.record_descriptors[0]

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        # Generate a Pydantic model for the input schema.
        input_model = generate_model_from_json_schema(
            json_schema=self.record_descriptor.input,
            class_name=input_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'semantic_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'tool': self.record_descriptor,
                'input': input_model,
                'vector_search': self.record_descriptor.vector_search,
                'secrets': self.record_descriptor.secrets[0].couchbase
            })
            logger.debug('The following code has been generated:\n' + rendered_code)

        # ...and write this as a single file to our output directory.
        output_file = output_dir / (uuid.uuid4().hex + '.py')
        with output_file.open('w') as fp:
            fp.write(rendered_code)
            fp.flush()
        return [output_file]


class HTTPRequestCodeGenerator(_BaseCodeGenerator):
    body_parameter_collision_handler: typing.Callable[[str], str] = pydantic.Field(default=lambda b: '_' + b)
    record_descriptors: list[HTTPRequestToolDescriptor] = pydantic.Field(min_length=1)

    @dataclasses.dataclass
    class InputContext:
        model: typing.Any
        json_schema: dict
        locations_dict: dict
        content_type: str = \
            openapi_parser.parser.ContentType.JSON

        @property
        def locations(self):
            return f'{json.dumps(self.locations_dict)}'

    @pydantic.field_validator('record_descriptors')
    @classmethod
    def record_descriptors_must_share_the_same_source(cls, v: list[RecordDescriptor]):
        if any(td.source != v[0].source for td in v):
            raise ValueError('Grouped HTTP-Request descriptors must share the same source!')
        return v

    def _create_json_schema_from_specification(self, operation: HTTPRequestToolDescriptor.OperationMetadata):
        # Our goal here is to create an easy "interface" for our LLM to call, so we will consolidate parameters
        # and the request body into one model.
        base_object = {
            'type': 'object',
            'properties': dict()
        }
        locations = dict()

        # Note: parent parameters are handled in the OperationMetadata class.
        for parameter in operation.parameters:
            base_object['properties'][parameter.name] = openapi_schema_to_json_schema.to_json_schema(
                schema=json.loads(json.dumps(parameter.schema, cls=HTTPRequestToolDescriptor.JSONEncoder))
            )
            locations[parameter.name] = parameter.location.value.lower()

        if operation.request_body is not None:
            json_type_request_content = None
            for content in operation.request_body.content:
                match content.type:
                    case openapi_parser.parser.ContentType.JSON:
                        json_type_request_content = content
                        break

                    # TODO (GLENN): Implement other descriptor of request bodies.
                    case _:
                        continue

            if json_type_request_content is None:
                logger.warning("No application/json content (specification) found in the request body!")
            else:
                from_request_body = openapi_schema_to_json_schema.to_json_schema(
                    schema=dataclasses.asdict(json_type_request_content.schema)
                )
                for k, v in from_request_body.items():
                    # If there are name collisions, we will rename the request body parameter.
                    if k in base_object['properties']:
                        parameter_name = self.body_parameter_collision_handler(k)
                    else:
                        parameter_name = k
                    base_object['properties'][parameter_name] = v
                    locations[parameter_name] = 'body'

        if len(base_object['properties']) == 0:
            return None
        else:
            return HTTPRequestCodeGenerator.InputContext(
                json_schema=base_object,
                locations_dict=locations,
                model=None
            )

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        # Iterate over our operations.
        output_modules = list()
        for record_descriptor in self.record_descriptors:
            operation = record_descriptor.operation

            # TODO (GLENN): We should try to build a model for the response (output) in the future.
            # Generate a Pydantic model for the input schema.
            input_context = self._create_json_schema_from_specification(operation)
            if input_context is not None:
                input_context.model = generate_model_from_json_schema(
                    json_schema=json.dumps(input_context.json_schema),
                    class_name=input_model_class_name_in_templates
                )

            # Instantiate our template...
            with (self.template_directory / 'httpreq_q.jinja').open('r') as tmpl_fp:
                template = jinja2.Template(source=tmpl_fp.read())
                generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
                rendered_code = template.render({
                    'time': generation_time,
                    'input': input_context,
                    'method': operation.method.upper(),
                    'path': operation.path,
                    'tool': record_descriptor,
                    'urls': [s.url for s in operation.servers]
                })
                logger.debug('The following code has been generated:\n' + rendered_code)

            # ...and write this as a single file to our output directory.
            output_file = output_dir / (uuid.uuid4().hex + '.py')
            with output_file.open('w') as fp:
                fp.write(rendered_code)
                fp.flush()
            output_modules.append(output_file)
        return output_modules
