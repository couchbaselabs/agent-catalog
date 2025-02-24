import click
import importlib
import logging
import os
import pathlib
import sys
import tempfile

from .find import SearchOptions
from .util import DASHES
from .util import KIND_COLORS
from .util import get_catalog
from agentc_cli.cmds.util import logging_command
from agentc_core.config import Config
from agentc_core.provider import ToolProvider
from agentc_core.record.descriptor import RecordDescriptor
from agentc_core.record.descriptor import RecordKind
from agentc_core.secrets import put_secret
from agentc_core.tool.descriptor import PythonToolDescriptor
from agentc_core.tool.descriptor import SemanticSearchToolDescriptor
from agentc_core.tool.descriptor import SQLPPQueryToolDescriptor
from agentc_core.tool.descriptor.secrets import CouchbaseSecrets
from pydantic import PydanticSchemaGenerationError
from pydantic import TypeAdapter

types_mapping = {"array": list, "integer": int, "number": float, "string": str}

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_execute(
    cfg: Config = None,
    *,
    query: str = None,
    name: str = None,
    include_dirty: bool = True,
    refiner: str = None,
    annotations: str = None,
    catalog_id: str = None,
    with_db: bool = False,
    with_local: bool = False,
):
    if cfg is None:
        cfg = Config()

    # Validate our search options.
    search_opt = SearchOptions(query=query, name=name)
    query, name = search_opt.query, search_opt.name
    click.secho(DASHES, fg=KIND_COLORS["tool"])

    # Determine what type of catalog we want.
    if with_local and with_db:
        force = "chain"
    elif with_db:
        force = "db"
    elif with_local:
        force = "local"
    else:
        raise ValueError("Either local FS or DB catalog must be specified!")

    # Initialize a catalog instance.
    catalog = get_catalog(cfg=cfg, force=force, include_dirty=include_dirty, kind="tool")

    # create temp directory for code dump
    _dir = cfg.codegen_output if cfg.codegen_output is not None else os.getcwd()
    with tempfile.TemporaryDirectory(dir=_dir) as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)

        # initialize tool provider
        provider = ToolProvider(
            catalog=catalog,
            output=tmp_dir_path,
            refiner=refiner,
        )

        # based on name or query get appropriate tool
        if name is not None:
            tool = provider.get(name, snapshot=catalog_id, annotations=annotations)
            if tool is None:
                raise ValueError(f"Tool {name} not found!") from None
        else:
            tools = provider.search(query, snapshot=catalog_id, annotations=annotations, limit=1)
            if len(tools) == 0:
                raise ValueError(f"No tool available for query {query}!")
            elif len(tools) > 1:
                logger.debug(f"Multiple tools found for query {query}. Using the first one.")
            else:
                tool = tools[0]

        # get tool metadata
        tool_metadata: RecordDescriptor = tool.meta

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
        except PydanticSchemaGenerationError as e:
            raise ValueError(
                f'Could not generate a schema for tool "{name}". '
                "Tool functions must have type hints that are compatible with Pydantic."
            ) from e

        # TODO (GLENN): We should try to directly import from the source first before writing the content.
        # if it is python tool get code from tool metadata and dump it into a file and import modules
        if tool_metadata.record_kind == RecordKind.PythonFunction:
            # create a file and dump python tool code into it
            python_tool_metadata: PythonToolDescriptor = tool_metadata
            file_name = python_tool_metadata.source.name
            with (tmp_dir_path / file_name).open("w") as f:
                f.write(python_tool_metadata.contents)

            # add temp directory and it's content as modules
            if str(tmp_dir_path.absolute()) not in sys.path:
                sys.path.append(str(tmp_dir_path.absolute()))
            gen_code_modules = importlib.import_module(python_tool_metadata.source.stem)

        # if it is sqlpp, yaml, jinja tools, provider dumps codes into a file by default, import that
        else:
            # add temp directory and it's content as modules
            if str(tmp_dir_path.absolute()) not in sys.path:
                sys.path.append(str(tmp_dir_path.absolute()))

            file_stems = [x.stem for x in (tmp_dir_path.iterdir()) if x.stem != "__init__"]
            file_stem = file_stems[1] if file_stems[0] == "__pycache__" else file_stems[0]
            gen_code_modules = importlib.import_module(file_stem)

        click.secho(DASHES, fg="yellow")
        click.secho("Instructions:", fg="blue")
        click.secho(
            message="\tPlease provide prompts for the prompted variables.\n"
            "\tThe types are shown for reference in parentheses.\n"
            "\tIf the input is of type list, please provide your list values in a comma-separated format.\n",
            fg="blue",
        )

        if tool_metadata.record_kind in [RecordKind.SQLPPQuery, RecordKind.SemanticSearch]:
            cb_tool_metadata: SQLPPQueryToolDescriptor | SemanticSearchToolDescriptor = tool_metadata
            cb_secrets: CouchbaseSecrets = cb_tool_metadata.secrets[0]
            cb_secrets_map = {
                cb_secrets.couchbase.conn_string: click.prompt(
                    click.style(cb_secrets.couchbase.conn_string + " (str)", fg="blue")
                ),
                cb_secrets.couchbase.username: click.prompt(
                    click.style(cb_secrets.couchbase.username + " (str)", fg="blue")
                ),
                cb_secrets.couchbase.password: click.prompt(
                    click.style(cb_secrets.couchbase.password + " (secret str)", fg="blue"), hide_input=True
                ),
            }
            for k, v in cb_secrets_map.items():
                put_secret(k, v)

        # prompt user for prompts
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
        click.secho(DASHES, fg="yellow")
        click.secho("Result:", fg="green")
        click.echo(res)
        click.secho(DASHES, fg=KIND_COLORS["tool"])


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
    except ValueError as e:
        logger.debug(f"Error {str(e)} is being swallowed.")
        is_correct = False

    while not is_correct:
        click.secho(f"Given value is not of type {list_type}. Please enter the correct values", fg="red")
        entered_val = click.prompt(click.style(f"{input_name} ({inp_type_to_show_user})", fg="blue"), type=str)
        try:
            conv_inps = split_and_convert(entered_val, types_mapping[list_type])
            is_correct = True
            return conv_inps
        except ValueError as e:
            logger.debug(f"Error {str(e)} is being swallowed.")
            is_correct = False
