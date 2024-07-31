import datetime
import pathlib
import typing
import uuid
import pydantic
import datamodel_code_generator.model
import datamodel_code_generator.parser.jsonschema
import jinja2
import subprocess
import abc
import re
import json
import yaml
import logging

from ..helper import (
    get_front_matter_from_dot_sqlpp
)
from ..descriptor import (
    ToolDescriptor,
    ToolKind
)

argument_model_class_name_in_templates = '_ArgumentInput'
output_model_class_name_in_templates = '_ToolOutput'
logger = logging.getLogger(__name__)


class _FromTemplateCodeGenerator(pydantic.BaseModel, abc.ABC):
    tool_descriptors: typing.List[ToolDescriptor]
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent / 'templates').resolve(),
        description='Location of the the template files.'
    )

    @staticmethod
    def _generate_model(json_schema: str, class_name: str) -> str:
        last_class_regex = re.compile(r'class \w+\((.*)\):(?!(\n|.)*class)')
        model_types = datamodel_code_generator.model.get_data_model_types(
            # TODO (GLENN): LangChain requires v1 Pydantic... hopefully they change this soon.
            datamodel_code_generator.DataModelType.PydanticBaseModel,
            target_python_version=datamodel_code_generator.PythonVersion.PY_311
        )

        # Generate a Pydantic model for the given JSON schema.
        argument_parser = datamodel_code_generator.parser.jsonschema.JsonSchemaParser(
            json_schema,
            data_model_type=model_types.data_model,
            data_model_root_type=model_types.root_model,
            data_model_field_type=model_types.field_model,
            data_type_manager_type=model_types.data_type_manager,
            dump_resolve_reference_action=model_types.dump_resolve_reference_action
        )
        generated_code = str(argument_parser.parse())

        # TODO (GLENN): There might be a better way to do this (using the JsonSchemaParser arguments).
        generated_code = generated_code \
            .replace('from __future__ import annotations', '') \
            .replace('from pydantic import BaseModel', 'from pydantic.v1 import BaseModel')
        return last_class_regex.sub(rf'class {class_name}(\1):', generated_code)

    @abc.abstractmethod
    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        pass


class SQLPPCodeGenerator(_FromTemplateCodeGenerator):
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
        argument_model_code = self._generate_model(
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
        output_model_code = self._generate_model(
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


class SemanticSearchCodeGenerator(_FromTemplateCodeGenerator):
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
        argument_model_code = self._generate_model(
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


class HTTPRequestCodeGenerator(_FromTemplateCodeGenerator):
    jar_location: pathlib.Path = pydantic.Field(
        description="Location of the OpenAPI generator JAR file."
    )
    java_command: typing.List[str] = pydantic.Field(
        default_factory=lambda: ['java', '-jar'],
        description="Java runtime to use when invoking the OpenAPI generator JAR."
    )
    generate_options: typing.List[str] = pydantic.Field(
        default_factory=lambda: [
            'generate',
            '-g', 'python',
            '--skip-operation-example',
            '--skip-validate-spec',
            '--global-property', 'apiDocs=false',
            '--global-property', 'modelDocs=false',
            '--global-property', 'apiTests=false',
            '--global-property', 'modelTests=false',
            '--additional-properties', 'generateSourceCodeOnly'
        ],
        description="Options used when invoking the OpenAPI generator JAR."
    )

    def generate(self, output_dir: pathlib.Path) -> typing.List[pathlib.Path]:
        # TODO (GLENN): We should add this check as a Pydantic validator.
        if any(td.source != self.tool_descriptors[0].source for td in self.tool_descriptors):
            raise ValueError('Grouped HTTP-Request descriptors must share the same source!')
        with self.tool_descriptors[0].source.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)

        # TODO (GLENN): Harden this.
        # Run the client generator using the source into a temporary folder.
        spec_file = parsed_desc['Open API']['File']
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
