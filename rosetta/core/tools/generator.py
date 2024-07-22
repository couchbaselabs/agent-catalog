import abc
import datetime
import pathlib
import typing
import pydantic
import datamodel_code_generator.model
import datamodel_code_generator.parser.jsonschema
import re
import json
import yaml
import logging

from .tooling import (
    ToolDescriptor,
    ToolKind
)

ArgumentModelClassNameInTemplates = '_ArgumentInput'
OutputModelClassNameInTemplates = '_ToolOutput'

logger = logging.getLogger(__name__)


class _SQLPPToolDescriptor(pydantic.BaseModel):
    name: str
    description: str
    sqlpp_query: str

    # In JSON-schema.
    parameters: typing.Dict
    output_schema: typing.Dict


class _SemanticSearchToolDescriptor(pydantic.BaseModel):
    name: str
    description: str

    # In JSON-schema.
    parameters: typing.Dict

    # For our vector search.
    bucket: str
    scope: str
    collection: str
    index: str
    vector_field: str
    text_field: str
    embedding_model: str


class _CodeGenerator(pydantic.BaseModel, abc.ABC):
    tool_descriptor: ToolDescriptor
    template_directory: pathlib.Path = pydantic.Field(
        default=(pathlib.Path(__file__).parent.parent / 'tmpl').resolve(),
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
    def write(self, fp):
        pass


class SQLPPCodeGenerator(_CodeGenerator):
    def _build_tool_descriptor(self) -> _SQLPPToolDescriptor:
        with self.tool_descriptor.source.open('r') as fp:
            # TODO (GLENN): Harden this step.
            front_lines = []
            is_scanning = False
            for line in fp:
                if line.strip().startswith('/*'):
                    is_scanning = True
                elif line.strip().endswith('*/'):
                    break
                elif is_scanning:
                    front_lines.append(line)
            front_matter = yaml.safe_load('\n'.join(front_lines))

            # Our SQL++ query is the entire file.
            sqlpp_query = fp.read()

            # Build our tool descriptor.
            return _SQLPPToolDescriptor(
                name=front_matter['Name'],
                description=front_matter['Description'].strip(),
                sqlpp_query=sqlpp_query,
                parameters=json.loads(front_matter['Parameters']),
                output_schema=json.loads(front_matter['Output'])
            )

    def write(self, fp):
        sqlpp_descriptor = self._build_tool_descriptor()

        # TODO (GLENN): Infer the output_schema in the future by first running the query.
        # Generate a Pydantic model for the argument and output schemas.
        argument_model_code = self._generate_model(
            json_schema=json.dumps(sqlpp_descriptor.parameters),
            class_name=ArgumentModelClassNameInTemplates
        )
        output_model_code = self._generate_model(
            json_schema=json.dumps(sqlpp_descriptor.output_schema),
            class_name=OutputModelClassNameInTemplates
        )

        # Instantiate our template.
        with (self.template_directory / 'sqlpp_q.template').open('r') as tmpl_fp:
            template_string = tmpl_fp.read()
            instance_string = template_string \
                .replace('<<GENERATION_DATE_PLACEHOLDER>>', datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')) \
                .replace('<<SQLPP_QUERY_PLACEHOLDER>>', sqlpp_descriptor.sqlpp_query) \
                .replace('<<ARGUMENT_SCHEMA_PLACEHOLDER>>', argument_model_code) \
                .replace('<<OUTPUT_SCHEMA_PLACEHOLDER>>', output_model_code) \
                .replace('<<TOOL_NAME_PLACEHOLDER>>', sqlpp_descriptor.name) \
                .replace('<<TOOL_DESCRIPTION_PLACEHOLDER>>', sqlpp_descriptor.description)
            logger.debug('The following code has been generated:\n' + instance_string)
            fp.write(instance_string)


class SemanticSearchCodeGenerator(_CodeGenerator):
    def _build_tool_descriptor(self) -> _SemanticSearchToolDescriptor:
        with self.tool_descriptor.source.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        assert parsed_desc['Tool Class'] == ToolKind.SemanticSearch
        return _SemanticSearchToolDescriptor(
            name=parsed_desc['Name'],
            description=parsed_desc['Description'].strip(),
            parameters=json.loads(parsed_desc['Parameters']),
            **parsed_desc['Vector Search']
        )

    def write(self, fp):
        sst_descriptor = self._build_tool_descriptor()

        # Generate a Pydantic model for the argument schema.
        argument_model_code = self._generate_model(
            json_schema=json.dumps(sst_descriptor.parameters),
            class_name=ArgumentModelClassNameInTemplates
        )

        # Instantiate our template...
        with (self.template_directory / 'semantic_q.template').open('r') as tmpl_fp:
            template_string = tmpl_fp.read()
            instance_string = template_string \
                .replace('<<GENERATION_DATE_PLACEHOLDER>>', datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')) \
                .replace('<<BUCKET_NAME_PLACEHOLDER>>', sst_descriptor.bucket) \
                .replace('<<SCOPE_NAME_PLACEHOLDER>>', sst_descriptor.scope) \
                .replace('<<COLLECTION_NAME_PLACEHOLDER>>', sst_descriptor.collection) \
                .replace('<<VECTOR_INDEX_NAME_PLACEHOLDER>>', sst_descriptor.index) \
                .replace('<<VECTOR_FIELD_NAME_PLACEHOLDER>>', sst_descriptor.vector_field) \
                .replace('<<TEXT_FIELD_NAME_PLACEHOLDER>>', sst_descriptor.text_field) \
                .replace('<<ARGUMENT_SCHEMA_PLACEHOLDER>>', argument_model_code) \
                .replace('<<EMBEDDING_MODEL_PLACEHOLDER>>', sst_descriptor.embedding_model) \
                .replace('<<TOOL_NAME_PLACEHOLDER>>', sst_descriptor.name) \
                .replace('<<TOOL_DESCRIPTION_PLACEHOLDER>>', sst_descriptor.description)
            logger.debug('The following code has been generated:\n' + instance_string)
            fp.write(instance_string)
