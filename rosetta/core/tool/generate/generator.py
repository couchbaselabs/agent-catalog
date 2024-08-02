import datetime
import pathlib
import typing
import uuid
import openapi_parser
import pydantic
import jinja2
import subprocess
import json
import abc
import yaml
import logging

from ..common import (
    get_front_matter_from_dot_sqlpp
)
from ..descriptor import (
    ToolDescriptor,
    ToolKind
)
from .common import (
    argument_model_class_name_in_templates,
    output_model_class_name_in_templates,
    generate_model_from_json_schema,
)

logger = logging.getLogger(__name__)


class _BaseCodeGenerator(pydantic.BaseModel):
    tool_descriptors: typing.List[ToolDescriptor]
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / 'templates').resolve(),
        description='Location of the the template files.'
    )

    @abc.abstractmethod
    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        pass


class SQLPPCodeGenerator(_BaseCodeGenerator):
    tool_descriptors: typing.List[ToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    class TemplateContext(pydantic.BaseModel):
        name: str
        description: str
        sqlpp_query: str

        # In JSON-schema.
        input_schema: typing.Dict
        output_schema: typing.Dict

    def _build_template_context(self) -> TemplateContext:
        front_matter = yaml.safe_load(get_front_matter_from_dot_sqlpp(self.tool_descriptors[0].source))
        with self.tool_descriptors[0].source.open('r') as fp:
            # Our SQL++ query is the entire file.
            sqlpp_query = fp.read()

            # Build our tool descriptor.
            return SQLPPCodeGenerator.TemplateContext(
                name=front_matter['Name'],
                description=front_matter['Description'].strip(),
                sqlpp_query=sqlpp_query,
                input_schema=json.loads(front_matter['Input']),
                output_schema=json.loads(front_matter['Output'])
            )

    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        template_context = self._build_template_context()

        # Generate a Pydantic model for the argument schema...
        argument_model_code = generate_model_from_json_schema(
            json_schema=json.dumps(template_context.input_schema),
            class_name=argument_model_class_name_in_templates
        )

        # ...and the output schema.
        # TODO (GLENN): Infer the output_schema in the future by first running the query.
        if template_context.output_schema['type'] == 'array':
            is_list_valued = True
            codegen_output_schema = template_context.output_schema['items']
        else:
            is_list_valued = False
            codegen_output_schema = template_context.output_schema
        output_model_code = generate_model_from_json_schema(
            json_schema=json.dumps(codegen_output_schema),
            class_name=output_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'sqlpp_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'list_valued': is_list_valued,
                'tool': template_context,
                'input_schema': {
                    'code': argument_model_code,
                    'name': argument_model_class_name_in_templates
                },
                'output_schema': {
                    'code': output_model_code,
                    'name': output_model_class_name_in_templates
                }
            })
            logger.debug('The following code has been generated:\n' + rendered_code)

        # ...and write this as a single file to our output directory.
        output_file = output_dir / (uuid.uuid4().hex + '.py')
        with output_file.open('w') as fp:
            fp.write(rendered_code)
            fp.flush()
        return [output_file]


class SemanticSearchCodeGenerator(_BaseCodeGenerator):
    tool_descriptors: typing.List[ToolDescriptor] = pydantic.Field(min_length=1, max_length=1)

    class TemplateContext(pydantic.BaseModel):
        name: str
        description: str

        # In JSON-schema.
        input_schema: typing.Dict

        # For our vector search.
        bucket: str
        scope: str
        collection: str
        index: str
        vector_field: str
        text_field: str
        embedding_model: str

    def _build_template_context(self) -> TemplateContext:
        with self.tool_descriptors[0].source.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        assert parsed_desc['Tool Class'] == ToolKind.SemanticSearch
        return SemanticSearchCodeGenerator.TemplateContext(
            name=parsed_desc['Name'],
            description=parsed_desc['Description'].strip(),
            input_schema=json.loads(parsed_desc['Input']),
            **parsed_desc['Vector Search']
        )

    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        template_context = self._build_template_context()

        # Generate a Pydantic model for the argument schema.
        argument_model_code = generate_model_from_json_schema(
            json_schema=json.dumps(template_context.input_schema),
            class_name=argument_model_class_name_in_templates
        )

        # Instantiate our template...
        with (self.template_directory / 'semantic_q.jinja').open('r') as tmpl_fp:
            template = jinja2.Template(source=tmpl_fp.read())
            generation_time = datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')
            rendered_code = template.render({
                'time': generation_time,
                'tool': template_context,
                'input_schema': {
                    'code': argument_model_code,
                    'name': argument_model_class_name_in_templates
                }
            })
            logger.debug('The following code has been generated:\n' + rendered_code)

        # ...and write this as a single file to our output directory.
        output_file = output_dir / (uuid.uuid4().hex + '.py')
        with output_file.open('w') as fp:
            fp.write(rendered_code)
            fp.flush()
        return [output_file]


class HTTPRequestCodeGenerator(_BaseCodeGenerator):
    class TemplateContext(pydantic.BaseModel):
        name: str


        # In JSON-schema.
        input_schema: typing.Dict
        output_schema: typing.Dict

    def _build_template_context(self) -> TemplateContext:
        front_matter = yaml.safe_load(get_front_matter_from_dot_sqlpp(self.tool_descriptors[0].source))
        with self.tool_descriptors[0].source.open('r') as fp:
            # Our SQL++ query is the entire file.
            sqlpp_query = fp.read()

            # Build our tool descriptor.
            return SQLPPCodeGenerator.TemplateContext(
                name=front_matter['Name'],
                description=front_matter['Description'].strip(),
                sqlpp_query=sqlpp_query,
                input_schema=json.loads(front_matter['Input']),
                output_schema=json.loads(front_matter['Output'])
            )

    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        # TODO (GLENN): We should add this check as a Pydantic validator.
        if any(td.source != self.tool_descriptors[0].source for td in self.tool_descriptors):
            raise ValueError('Grouped HTTP-Request descriptors must share the same source!')
        with self.tool_descriptors[0].source.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        spec_file = parsed_desc['Open API']['File']

        # From the spec, find all relevant operations.
        parsed_spec = openapi_parser.parse(pathlib.Path(spec_file).absolute())



        parsed_spec.paths[0].operations[0].parameters


        # TODO (GLENN): Harden this.
        # Run the client generator using the source into a temporary folder.
        jar_output = uuid.uuid4().hex
        jar_command = \
            self.java_command + \
            [self.jar_location.absolute()] + \
            self.generate_options + \
            ['-o', (output_dir / jar_output).absolute()] + \
            ['-i', spec_file] + \
            ['--additional-properties', 'packageName=' + pathlib.Path(spec_file).stem]
        subprocess.run(jar_command)
        return []
