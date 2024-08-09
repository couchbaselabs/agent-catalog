import datetime
import pathlib
import typing
import uuid
import openapi_parser.parser
import pydantic
import jinja2
import json
import abc
import yaml
import logging
import dataclasses
import openapi_schema_to_json_schema

from .common import (
    input_model_class_name_in_templates,
    output_model_class_name_in_templates,
    generate_model_from_json_schema,
)
from ..models import (
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)
from ...record.descriptor import RecordDescriptor

logger = logging.getLogger(__name__)


class _BaseCodeGenerator(pydantic.BaseModel):
    record_descriptors: list[RecordDescriptor] = pydantic.Field(min_length=1)
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / 'templates').resolve(),
        description='Location of the the template files.'
    )

    @abc.abstractmethod
    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[RecordDescriptor] = pydantic.Field(min_length=1, max_length=1)

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        sqlpp_file = self.record_descriptors[0].source
        metadata = SQLPPQueryMetadata.model_validate(
            SQLPPQueryMetadata.read_front_matter(sqlpp_file)
        )
        with sqlpp_file.open('r') as fp:
            sqlpp_query = fp.read()

        # Generate a Pydantic model for the input schema...
        input_model = generate_model_from_json_schema(
            json_schema=metadata.input,
            class_name=input_model_class_name_in_templates
        )

        # ...and the output schema.
        output_model = generate_model_from_json_schema(
            json_schema=metadata.output,
            class_name=output_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'sqlpp_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'sqlpp_query': sqlpp_query,
                'tool_metadata': metadata,
                'input': input_model,
                'output': output_model
            })
            logger.debug('The following code has been generated:\n' + rendered_code)

        # ...and write this as a single file to our output directory.
        output_file = output_dir / (uuid.uuid4().hex + '.py')
        with output_file.open('w') as fp:
            fp.write(rendered_code)
            fp.flush()
        return [output_file]


class SemanticSearchCodeGenerator(_BaseCodeGenerator):
    record_descriptors: list[RecordDescriptor] = pydantic.Field(min_length=1, max_length=1)

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        yaml_file = self.record_descriptors[0].source
        metadata = SemanticSearchMetadata.model_validate(yaml.safe_load(yaml_file.open()))

        # Generate a Pydantic model for the input schema.
        input_model = generate_model_from_json_schema(
            json_schema=metadata.input,
            class_name=input_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'semantic_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'tool_metadata': metadata,
                'input': input_model
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

    def _create_json_schema_from_specification(self, operation: HTTPRequestMetadata.OpenAPIMetadata.OperationMetadata):
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
                schema=json.loads(json.dumps(parameter.schema, cls=HTTPRequestMetadata.JSONEncoder))
            )
            locations[parameter.name] = parameter.location.value.lower()

        if operation.specification.request_body is not None:
            json_type_request_content = None
            for content in operation.specification.request_body.content:
                match content.type:
                    case openapi_parser.parser.ContentType.JSON:
                        json_type_request_content = content
                        break

                    # TODO (GLENN): Implement other models of request bodies.
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
        yaml_file = self.record_descriptors[0].source
        metadata = HTTPRequestMetadata.model_validate(yaml.safe_load(yaml_file.open()))

        # Iterate over our operations.
        output_modules = list()
        for operation in metadata.open_api.operations:
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
                    'openapi': operation,
                    'input': input_context,
                    'method': operation.method.upper(),
                    'path': operation.path,
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
