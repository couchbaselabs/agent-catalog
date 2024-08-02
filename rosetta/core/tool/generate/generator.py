import datetime
import pathlib
import uuid
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
from ..types import (
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)
from ...catalog.descriptor import ToolDescriptor
from ..common import get_front_matter_from_dot_sqlpp

logger = logging.getLogger(__name__)


class _BaseCodeGenerator(pydantic.BaseModel):
    tool_descriptors: list[ToolDescriptor]
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / 'templates').resolve(),
        description='Location of the the template files.'
    )

    @abc.abstractmethod
    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    tool_descriptors: list[ToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        sqlpp_file = self.tool_descriptors[0].source
        metadata = SQLPPQueryMetadata.model_validate(
            yaml.safe_load(get_front_matter_from_dot_sqlpp(sqlpp_file))
        )
        with sqlpp_file.open('r') as fp:
            sqlpp_query = fp.read()

        # Generate a Pydantic model for the input schema...
        input_model = generate_model_from_json_schema(
            json_schema=json.dumps(metadata.input),
            class_name=input_model_class_name_in_templates
        )

        # ...and the output schema.
        output_model = generate_model_from_json_schema(
            json_schema=json.dumps(metadata.output),
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
    tool_descriptors: list[ToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        yaml_file = self.tool_descriptors[0].source
        metadata = SemanticSearchMetadata.model_validate(yaml.safe_load(yaml_file))

        # Generate a Pydantic model for the input schema.
        input_model = generate_model_from_json_schema(
            json_schema=json.dumps(metadata.input),
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
    @pydantic.field_validator('tool_descriptors')
    @classmethod
    def tool_descriptors_must_share_the_same_source(cls, v: list[ToolDescriptor]):
        if any(td.source != v[0].source for td in v):
            raise ValueError('Grouped HTTP-Request descriptors must share the same source!')

    @staticmethod
    def _create_json_schema_from_parameters(parameters: dict):
        if len(parameters) == 0:
            return None

        base_object = {'type': 'object', 'properties': dict()}
        for name, parameter in parameters.items():
            base_object['properties'][name] = openapi_schema_to_json_schema.to_json_schema(
                schema=dataclasses.asdict(parameter)
            )
        return base_object

    def generate(self, output_dir: pathlib.Path) -> list[pathlib.Path]:
        yaml_file = self.tool_descriptors[0].source
        metadata = HTTPRequestMetadata.model_validate(yaml.safe_load(yaml_file))

        # Iterate over our operations.
        output_modules = list()
        for operation in metadata.open_api.operations:
            # TODO (GLENN): We should try to build a model for the response (output) in the future.
            # Generate a Pydantic model for the input schema.
            input_schema = self._create_json_schema_from_parameters(operation.parameters)
            if input_schema is not None:
                input_model = generate_model_from_json_schema(
                    json_schema=json.dumps(input_schema),
                    class_name=input_model_class_name_in_templates
                )
            else:
                input_model = None

            # Instantiate our template...
            with (self.template_directory / 'httpreq_q.jinja').open('r') as tmpl_fp:
                template = jinja2.Template(source=tmpl_fp.read())
                generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
                rendered_code = template.render({
                    'time': generation_time,
                    'tool_metadata': metadata,
                    'input': input_model,
                    'method': operation.method.upper(),
                    'path': operation.path,
                    'urls': operation.servers
                })
                logger.debug('The following code has been generated:\n' + rendered_code)

            # ...and write this as a single file to our output directory.
            output_file = output_dir / (uuid.uuid4().hex + '.py')
            with output_file.open('w') as fp:
                fp.write(rendered_code)
                fp.flush()
            output_modules.append(output_file)
        return output_modules
