import datamodel_code_generator.model
import datamodel_code_generator.parser.jsonschema
import datamodel_code_generator.parser.openapi
import json
import pydantic
import re

INPUT_MODEL_CLASS_NAME_IN_TEMPLATES = "ArgumentInput"
OUTPUT_MODEL_CLASS_NAME_IN_TEMPLATES = "ToolOutput"


class GeneratedCode(pydantic.BaseModel):
    generated_code: str
    is_list_valued: bool
    type_name: str


def _post_process_model_code(generated_code: str, class_name: str) -> str:
    # Because we are only using a snippet of the generated code, we need to remove this.
    without_future_import = generated_code.replace("from __future__ import annotations", "")

    # We need to find the last class in the generated code (this might be fragile).
    with_replaced_name = re.sub(
        pattern=r"class \w+(\(?.*\)?)(:[\s\S]*?(?=class|\Z))",
        repl=rf"class {class_name}\1\2",
        string=without_future_import,
        flags=re.MULTILINE,
    )
    return with_replaced_name


def generate_model_from_json_schema(
    json_schema: dict,
    class_name: str,
    python_version: datamodel_code_generator.PythonVersion,
    model_type: datamodel_code_generator.DataModelType,
) -> GeneratedCode:
    model_types = datamodel_code_generator.model.get_data_model_types(
        data_model_type=model_type,
        target_python_version=python_version,
        # TODO (GLENN): We might need to expose this as a parameter in the future.
        target_datetime_class=datamodel_code_generator.DatetimeClassType.Datetime,
    )

    # If we have a list-valued field, first extract the fields involved.
    if json_schema["type"] == "array":
        codegen_schema = json_schema["items"]
        is_list_valued = True
        type_name = class_name
    else:
        codegen_schema = json_schema
        is_list_valued = False
        type_name = class_name

    # Generate a Pydantic model for the given JSON schema.
    argument_parser = datamodel_code_generator.parser.jsonschema.JsonSchemaParser(
        json.dumps(codegen_schema),
        data_model_type=model_types.data_model,
        data_model_root_type=model_types.root_model,
        data_model_field_type=model_types.field_model,
        data_type_manager_type=model_types.data_type_manager,
        dump_resolve_reference_action=model_types.dump_resolve_reference_action,
        class_name=class_name,
    )
    generated_code = _post_process_model_code(str(argument_parser.parse()), class_name)
    return GeneratedCode(generated_code=generated_code, is_list_valued=is_list_valued, type_name=type_name)
