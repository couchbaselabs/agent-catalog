import click
import os
import pathlib

from ..models import Context
from agentc_core.catalog import CatalogMem
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME
from agentc_core.provider import ToolProvider
from pydantic import PydanticSchemaGenerationError
from pydantic import TypeAdapter

types_mapping = {"array": list, "integer": int, "number": float, "string": str}


def cmd_execute(ctx: Context, name: str | None, query: str | None):
    catalog_path = pathlib.Path(ctx.catalog) / DEFAULT_TOOL_CATALOG_NAME
    catalog = CatalogMem.load(catalog_path)

    provider = ToolProvider(catalog, output=pathlib.Path(os.path.join(os.getcwd(), "codes")))
    tool = None
    if name is not None:
        tool = provider.get(name)
        if tool is None:
            raise ValueError(f"Tool {name} not found!") from None
    else:
        tools = provider.search(query, limit=1)
        if len(tools) == 0:
            raise ValueError(f"No tool available for query {query}!") from None
        else:
            tool = tools[0]

    try:
        parameters = TypeAdapter(tool).json_schema()
        class_types = dict()
        if "$defs" in parameters:
            class_types = get_types_for_classes(parameters["$defs"])
        print(class_types)
        input_types = dict()
        for param, param_def in parameters["properties"].items():
            if "$ref" in param_def:
                input_types[param] = class_types[param_def["$ref"].split("/")[-1]]
            elif param_def["type"] == "array":
                input_types[param] = list(types_mapping[param_def["items"]["type"]])
            else:
                input_types[param] = types_mapping[param_def["type"]]
    except PydanticSchemaGenerationError:
        raise ValueError(
            f'Could not generate a schema for tool "{name}". '
            "Tool functions must have type hints that are compatible with Pydantic."
        ) from None

    user_inputs = take_input_from_user(input_types)

    res = tool(**user_inputs)
    click.secho("Result:", fg="green")
    click.echo(res)


def get_types_for_classes(class_defs: dict) -> dict:
    class_types = dict()
    for class_name, class_def in class_defs.items():
        class_types[class_name] = dict()
        for member_name, member_def in class_def["properties"].items():
            if member_def["type"] == "array":
                class_types[class_name][member_name] = list(types_mapping[member_def["items"]["type"]])
            else:
                class_types[class_name][member_name] = types_mapping[member_def["type"]]
    return class_types


def take_input_from_user(input_types: dict) -> dict:
    user_inputs = dict()
    for inp, inp_type in input_types.items():
        if isinstance(inp_type, dict):
            user_inputs[inp] = dict()
            for inp_member, inp_member_type in inp_type.items():
                is_list = inp_member_type in [list[str], list[int], list[float]]
                entered_val = click.prompt(f"{inp_member}", type=str if is_list else inp_member_type)
                if not is_list:
                    user_inputs[inp][inp_member] = entered_val
                    continue

                list_type = "string"
                if inp_member_type == list[int]:
                    list_type = "integer"
                elif inp_member_type == list[float]:
                    list_type = "number"

                is_correct = True
                try:
                    conv_inps = split_and_convert(entered_val, types_mapping[list_type])
                    user_inputs[inp][inp_member] = conv_inps
                    continue
                except ValueError:
                    is_correct = False

                while not is_correct:
                    click.echo(f"All entered values are not of type {list_type}! Enter correct values")
                    entered_val = click.prompt(f"{inp_member}", type=str if is_list else inp_member_type)
                    try:
                        conv_inps = split_and_convert(entered_val, types_mapping[list_type])
                        is_correct = True
                        user_inputs[inp][inp_member] = conv_inps
                        break
                    except ValueError:
                        is_correct = False

        else:
            entered_val = click.prompt(f"{inp}", type=inp_type)
            user_inputs[inp] = entered_val
    return user_inputs


def split_and_convert(entered_val: str, target_type):
    conv_inps = []
    for element in entered_val.split(","):
        element = element.strip()
        conv_inps.append(target_type(element))
    return conv_inps
