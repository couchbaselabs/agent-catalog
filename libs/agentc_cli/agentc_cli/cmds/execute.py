import click
import importlib
import os
import pathlib
import tempfile

from ..models import Context
from agentc_core.catalog import CatalogMem
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME
from agentc_core.embedding.embedding import EmbeddingModel
from agentc_core.provider import ToolProvider
from pydantic import PydanticSchemaGenerationError
from pydantic import TypeAdapter

types_mapping = {"array": list, "integer": int, "number": float, "string": str}


def cmd_execute(ctx: Context, name: str | None, query: str | None, embedding_model: EmbeddingModel):
    # get local catalog
    catalog_path = pathlib.Path(ctx.catalog) / DEFAULT_TOOL_CATALOG_NAME
    catalog = CatalogMem(catalog_path=catalog_path, embedding_model=embedding_model)

    # create temp directory for code dump
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmp_dir:
        tmp_dir_name = tmp_dir.split("/")[-1]
        provider = ToolProvider(catalog, output=pathlib.Path(tmp_dir), decorator=lambda x: x)

        # based on name or query get appropriate tool
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

        # get tool metadata
        tool_metadata = tool.meta

        # extract all variables that user needs to provide as input for tool
        try:
            parameters = TypeAdapter(tool.func).json_schema()
            class_types = dict()
            # get types for all custom defined classes
            if "$defs" in parameters:
                class_types = get_types_for_classes(parameters["$defs"])
            input_types = dict()
            for param, param_def in parameters["properties"].items():
                # class type
                if "$ref" in param_def:
                    input_types[param] = class_types[param_def["$ref"].split("/")[-1]]
                # list type
                elif param_def["type"] == "array":
                    param_def_items = param_def["items"]
                    input_types[param] = list[types_mapping[param_def_items["type"]]]
                # other types like str, int, float
                else:
                    input_types[param] = types_mapping[param_def["type"]]
        except PydanticSchemaGenerationError:
            raise ValueError(
                f'Could not generate a schema for tool "{name}". '
                "Tool functions must have type hints that are compatible with Pydantic."
            ) from None

        # if it is python tool get code from tool metadata and dump it into a file and import modules
        if ".py" in str(tool_metadata.source):
            # create a file and dump python tool code into it
            file_name = f"{name}.py"
            file_path = os.path.join(tmp_dir, file_name)
            with open(file_path, "w") as f:
                f.write(tool_metadata.contents)
            # import modules from the created file
            gen_code_modules = importlib.import_module(f"{tmp_dir_name}.{name}")
        # if it is sqlpp, yaml, jinja tools, provider dumps codes into a file by default, import that
        else:
            # get file name of template generated code
            file_name = os.listdir(tmp_dir)[0]
            file_module_name = file_name.split(".")[0]
            # import modules from provider created file
            gen_code_modules = importlib.import_module(f"{tmp_dir_name}.{file_module_name}")

        click.echo(
            "Provide inputs for the prompted variables, types are shown for reference in parenthesis\n"
            "If input is of type list then provide values separated by a comma.\n"
        )
        # prompt user for inputs
        user_inputs = take_input_from_user(input_types)

        # if user has any variable which is of object type, create it from class
        modified_user_inputs = dict()
        for variable, user_input in user_inputs.items():
            if isinstance(user_input, dict) and "$ref" in parameters["properties"][variable]:
                custom_class_name = parameters["properties"][variable]["$ref"].split("/")[-1]
                class_needed = getattr(gen_code_modules, custom_class_name)
                modified_user_inputs[variable] = class_needed(**user_input)
            else:
                modified_user_inputs[variable] = user_input

        # call tool function
        res = tool.func(**modified_user_inputs)
        click.secho("\nResult:", fg="green")
        click.echo(res)


# gets all class variable types present in all custom defined classes in code
def get_types_for_classes(class_defs: dict) -> dict:
    class_types = dict()
    for class_name, class_def in class_defs.items():
        class_types[class_name] = dict()
        for member_name, member_def in class_def["properties"].items():
            if member_def["type"] == "array":
                member_def_items = member_def["items"]
                class_types[class_name][member_name] = list[types_mapping[member_def_items["type"]]]
            else:
                class_types[class_name][member_name] = types_mapping[member_def["type"]]
    return class_types


# takes input from user based on the types provided
def take_input_from_user(input_types: dict) -> dict:
    user_inputs = dict()
    for inp, inp_type in input_types.items():
        if isinstance(inp_type, dict):
            user_inputs[inp] = take_input_from_user(inp_type)
        else:
            is_list = inp_type in [list[str], list[int], list[float], list]
            inp_type_to_show_user = (
                f"{inp_type.__origin__.__name__} [{', '.join(arg.__name__ for arg in inp_type.__args__)}]"
                if is_list
                else inp_type.__name__
            )

            entered_val = click.prompt(
                click.style(f"{inp} ({inp_type_to_show_user})", fg="blue"), type=str if is_list else inp_type
            )

            if not is_list:
                user_inputs[inp] = entered_val
            else:
                user_inputs[inp] = take_verify_list_inputs(entered_val, inp, inp_type, inp_type_to_show_user)

    return user_inputs


# extract each value from comma separated values and convert to desired type
def split_and_convert(entered_val: str, target_type):
    conv_inps = []
    for element in entered_val.split(","):
        element = element.strip()
        conv_inps.append(target_type(element))
    return conv_inps


# when initial comma separated values are given, they are verified and prompted again if they are not correct
def take_verify_list_inputs(entered_val, input_name, input_type, inp_type_to_show_user):
    list_type = "string"
    if input_type == list[int]:
        list_type = "integer"
    elif input_type == list[float]:
        list_type = "number"

    # check if all comma separated values are of desired type
    # else keep asking in the loop till correct values are given
    is_correct = True
    try:
        conv_inps = split_and_convert(entered_val, types_mapping[list_type])
        return conv_inps
    except ValueError:
        is_correct = False

    while not is_correct:
        click.secho(f"All entered values are not of type {list_type}! Enter correct values", fg="red")
        entered_val = click.prompt(click.style(f"{input_name} ({inp_type_to_show_user})", fg="blue"), type=str)
        try:
            conv_inps = split_and_convert(entered_val, types_mapping[list_type])
            is_correct = True
            return conv_inps
        except ValueError:
            is_correct = False
