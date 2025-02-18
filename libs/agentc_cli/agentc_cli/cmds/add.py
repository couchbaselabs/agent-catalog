import click
import datetime
import jinja2
import logging
import os
import pathlib
import platform
import subprocess
import typing

from .util import logging_command
from agentc_core.config import Config
from agentc_core.record.descriptor import RecordKind

logger = logging.getLogger(__name__)

if os.environ.get("EDITOR"):
    default_editor = os.environ.get("EDITOR")
elif os.environ.get("VISUAL"):
    default_editor = os.environ.get("VISUAL")
elif platform.system() == "Windows":
    default_editor = "notepad"
else:
    default_editor = "vi"


def _get_name_and_description() -> tuple[str, str]:
    name = click.prompt("Name", type=str)
    while not name.isidentifier():
        click.secho("Name must be a valid Python identifier.", fg="red")
        name = click.prompt("Name", type=str)
    description = click.prompt("Description", type=str)
    return name, description


def add_model_input(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("model_input.jinja")
    click.echo("Type: model_input")

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
    click.secho(f"Model input written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_http_request(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("http_request.jinja")
    click.echo("Type: http_request")

    # Prompt for our additional fields.
    filename = click.prompt("Filename", type=str)
    spec_filename = click.prompt("OpenAPI Filename", type=pathlib.Path, default="NO PATH")
    spec_url = click.prompt("OpenAPI URL", type=str, default="NO URL") if spec_filename == "NO PATH" else "NO URL"
    while spec_url == "NO URL" and spec_filename == "NO PATH":
        click.secho("You must provide either a URL or a filename.", fg="red")
        spec_filename = click.prompt("OpenAPI Filename", type=pathlib.Path, default="NO PATH")
        spec_url = click.prompt("OpenAPI URL", type=str, default="NO URL") if spec_filename == "NO PATH" else "NO URL"

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
    click.secho(f"HTML request tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_python_function(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("python_function.jinja")
    click.echo("Type: python_function")

    # Prompt for our additional fields.
    name, description = _get_name_and_description()

    # Render and write our template.
    rendered = template.render(
        name=name, description=description, timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    )
    output_file = output / f"{name}.py"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click.secho(f"Python (function) tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_semantic_search(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("semantic_search.jinja")
    click.echo("Type: semantic_search")

    # TODO (GLENN): We can use click.Choice in the future so user's don't have to go searching for these names.
    # Prompt for our additional fields.
    name, description = _get_name_and_description()
    bucket = click.prompt("Bucket", type=str)
    scope = click.prompt("Scope", type=str)
    collection = click.prompt("Collection", type=str)
    index = click.prompt("Index Name", type=str)
    vector_field = click.prompt("Vector Field", type=str)
    text_field = click.prompt("Text Field", type=str)
    embedding_model = click.prompt("Embedding Model", type=str)

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
    click.secho(f"Semantic search tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


def add_sqlpp_query(output: pathlib.Path, template_env: jinja2.Environment):
    template = template_env.get_template("sqlpp_query.jinja")
    click.echo("Type: sqlpp_query")

    # Prompt for our additional fields.
    name, description = _get_name_and_description()

    # Render and write our template.
    rendered = template.render(
        name=name, description=description, timestamp=datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    )
    output_file = output / f"{name}.sqlpp"
    with output_file.open("w") as fp:
        fp.write(rendered)
    click.secho(f"SQL++ query tool written to: {output_file}", fg="green")
    subprocess.run([default_editor, f"{output_file}"])


@logging_command(parent_logger=logger)
def cmd_add(
    cfg: Config = None,
    *,
    output: pathlib.Path,
    kind: RecordKind
    | typing.Literal["model_input", "http_request", "python_function", "semantic_search", "sqlpp_query"],
):
    if cfg is None:
        cfg = Config()

    inputs_template_loader = jinja2.PackageLoader("agentc_core.inputs")
    tool_template_loader = jinja2.PackageLoader("agentc_core.tool")
    template_env = jinja2.Environment(loader=jinja2.ChoiceLoader([inputs_template_loader, tool_template_loader]))
    click.secho(f"Now building a new tool / input file. The output will be saved to: {output}", fg="yellow")

    match kind:
        case RecordKind.ModelInput | "model_input":
            add_model_input(output, template_env)
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
