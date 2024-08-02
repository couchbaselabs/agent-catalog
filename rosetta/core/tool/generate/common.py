import datamodel_code_generator.model
import datamodel_code_generator.parser.jsonschema
import datamodel_code_generator.parser.openapi
import json
import pydantic

input_model_class_name_in_templates = '_ArgumentInput'
output_model_class_name_in_templates = '_ToolOutput'


class GeneratedPydanticCode(pydantic.BaseModel):
    generated_code: str
    is_list_valued: bool
    type_name: str


def _post_process_model_code(generated_code: str) -> str:
    return (
        generated_code
        # This should not appear in the output (this is most likely a bug in datamodel_code_generator).
        .replace('from __future__ import annotations', '')
        # This is to satisfy LangChain's dependency on Pydantic v1.
        .replace('from pydantic import BaseModel', 'from pydantic.v1 import BaseModel')
    )


def generate_model_from_json_schema(json_schema: dict, class_name: str) -> GeneratedPydanticCode:
    model_types = datamodel_code_generator.model.get_data_model_types(
        # TODO (GLENN): LangChain requires v1 Pydantic... hopefully they change this soon.
        datamodel_code_generator.DataModelType.PydanticBaseModel,
        target_python_version=datamodel_code_generator.PythonVersion.PY_311
    )

    # If we have a list-valued field, first extract the fields involved.
    if json_schema['type'] == 'array':
        codegen_schema = json_schema['items']
        is_list_valued = True
        type_name = class_name
    else:
        codegen_schema = json_schema
        is_list_valued = False
        type_name = class_name

    # Generate a Pydantic model for the given JSON schema.
    argument_parser = datamodel_code_generator.parser.jsonschema.JsonSchemaParser(
        json.loads(codegen_schema),
        data_model_type=model_types.data_model,
        data_model_root_type=model_types.root_model,
        data_model_field_type=model_types.field_model,
        data_type_manager_type=model_types.data_type_manager,
        dump_resolve_reference_action=model_types.dump_resolve_reference_action,
        class_name=class_name,
    )
    return GeneratedPydanticCode(
        generated_code=_post_process_model_code(str(argument_parser.parse())),
        is_list_valued=is_list_valued,
        type_name=type_name
    )
