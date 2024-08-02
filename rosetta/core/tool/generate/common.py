import datamodel_code_generator.model
import datamodel_code_generator.parser.jsonschema
import datamodel_code_generator.parser.openapi

argument_model_class_name_in_templates = '_ArgumentInput'
output_model_class_name_in_templates = '_ToolOutput'


def _post_process_model_code(generated_code: str) -> str:
    return (
        generated_code
        # This should not appear in the output (this is most likely a bug in datamodel_code_generator).
        .replace('from __future__ import annotations', '')
        # This is to satisfy LangChain's dependency on Pydantic v1.
        .replace('from pydantic import BaseModel', 'from pydantic.v1 import BaseModel')
    )


def generate_model_from_json_schema(json_schema: str, class_name: str) -> str:
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
        dump_resolve_reference_action=model_types.dump_resolve_reference_action,
        class_name=class_name,
    )
    return _post_process_model_code(str(argument_parser.parse()))
