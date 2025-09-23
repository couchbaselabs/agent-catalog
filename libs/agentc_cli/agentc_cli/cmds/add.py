import click_extra
import datetime
import jinja2
import logging
import os
import pathlib
import platform
import re
import subprocess
import typing

from .util import logging_command
from agentc_core.config import Config
from agentc_core.record.descriptor import RecordKind

logger = logging.getLogger(__name__)


def _is_safe_editor_command(cmd: str) -> bool:
    return bool(cmd) and not re.search(r'[;&|<>$`\\"\'\s]', cmd)


_editor_from_environment = os.environ.get("EDITOR")
_visual_from_environment = os.environ.get("VISUAL")

if _editor_from_environment and _is_safe_editor_command(_editor_from_environment):
    default_editor = _editor_from_environment
elif _visual_from_environment and _is_safe_editor_command(_visual_from_environment):
    default_editor = _visual_from_environment
elif platform.system() == "Windows":
    default_editor = "notepad"
else:
    default_editor = "vi"


def _get_name_and_description() -> tuple[str, str]:
    name = click_extra.prompt("Name", type=str)
    while not name.isidentifier():
        click_extra.secho("Name must be a valid Python identifier.", fg="red")
        name = click_extra.prompt("Name", type=str)
    description = click_extra.prompt("Description", type=str)
    return name, description


def add_prompt(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("prompt.jinja")
    click_extra.echo("Type: prompt")

    # Prompt for our additional fields.
    name, description = _get_name_and_description()

    # Render and write our template.
    rendered = template.render(
        input_name=name,
        input_description=description,
    )
    output_file = output / f"{name}.yaml"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click_extra.secho(f"Prompt written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_http_request(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("http_request.jinja")
    click_extra.echo("Type: http_request")

    # Prompt for our additional fields.
    filename = click_extra.prompt("Filename", type=str)
    spec_filename = click_extra.prompt("OpenAPI Filename", type=pathlib.Path, default="NO PATH")
    spec_url = click_extra.prompt("OpenAPI URL", type=str, default="NO URL") if spec_filename == "NO PATH" else "NO URL"
    while spec_url == "NO URL" and spec_filename == "NO PATH":
        click_extra.secho("You must provide either a URL or a filename.", fg="red")
        spec_filename = click_extra.prompt("OpenAPI Filename", type=pathlib.Path, default="NO PATH")
        spec_url = (
            click_extra.prompt("OpenAPI URL", type=str, default="NO URL") if spec_filename == "NO PATH" else "NO URL"
        )

    # Render and write our template.
    if spec_filename != "NO PATH":
        rendered = template.render(
            filename=spec_filename, timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
        )
    else:
        rendered = template.render(url=spec_url)
    output_file = output / f"{filename}.yaml"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click_extra.secho(f"HTML request tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_python_function(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("python_function.jinja")
    click_extra.echo("Type: python_function")

    # Prompt for our additional fields.
    name, description = _get_name_and_description()

    # Render and write our template.
    rendered = template.render(
        name=name, description=description, timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    )
    output_file = output / f"{name}.py"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click_extra.secho(f"Python (function) tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_semantic_search(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("semantic_search.jinja")
    click_extra.echo("Type: semantic_search")

    # TODO (GLENN): We can use click_extra.Choice in the future so user's don't have to go searching for these names.
    # Prompt for our additional fields.
    name, description = _get_name_and_description()
    bucket = click_extra.prompt("Bucket", type=str)
    scope = click_extra.prompt("Scope", type=str)
    collection = click_extra.prompt("Collection", type=str)
    index = click_extra.prompt("Index Name", type=str)
    vector_field = click_extra.prompt("Vector Field", type=str)
    text_field = click_extra.prompt("Text Field", type=str)
    embedding_model = click_extra.prompt("Embedding Model", type=str)

    # Render and write our template.
    rendered = template.render(
        name=name,
        description=description,
        bucket=bucket,
        scope=scope,
        collection=collection,
        index=index,
        vector_field=vector_field,
        text_field=text_field,
        embedding_model=embedding_model,
        timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"),
    )
    output_file = output / f"{name}.yaml"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click_extra.secho(f"Semantic search tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_sqlpp_query(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("sqlpp_query.jinja")
    click_extra.echo("Type: sqlpp_query")

    # Prompt for our additional fields.
    name, description = _get_name_and_description()

    # Render and write our template.
    rendered = template.render(
        name=name, description=description, timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    )
    output_file = output / f"{name}.sqlpp"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click_extra.secho(f"SQL++ query tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


@logging_command(logger)
def cmd_add(
    cfg: Config = None,
    *,
    output: pathlib.Path,
    kind: RecordKind | typing.Literal["prompt", "http_request", "python_function", "semantic_search", "sqlpp_query"],
):
    if cfg is None:
        cfg = Config()

    prompt_template_loader = jinja2.PackageLoader("agentc_core.prompt")
    tool_template_loader = jinja2.PackageLoader("agentc_core.tool")
    template_env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([prompt_template_loader, tool_template_loader]), autoescape=True
    )
    click_extra.secho(f"Now building a new tool / prompt file. The output will be saved to: {output}", fg="yellow")

    match kind:
        case RecordKind.Prompt | "prompt":
            add_prompt(output, template_env)
        case RecordKind.HTTPRequest | "http_request":
            add_http_request(output, template_env)
        case RecordKind.PythonFunction | "python_function":
            add_python_function(output, template_env)
        case RecordKind.SemanticSearch | "semantic_search":
            add_semantic_search(output, template_env)
        case RecordKind.SQLPPQuery | "sqlpp_query":
            add_sqlpp_query(output, template_env)
        case _:
            # We should never reach here.
            raise ValueError(f"Unsupported record kind: {kind}!")
