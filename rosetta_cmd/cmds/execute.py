import click
import controlflow as cf
import os
import pathlib

from ..defaults import DEFAULT_TOOL_CATALOG_NAME
from ..models import Context
from rosetta_core.catalog import CatalogMem

supported_providers = ["openai", "azure-openai", "anthropic", "google", "groq"]


def cmd_execute(ctx: Context, name: str, model: str):
    catalog_path = pathlib.Path(ctx.catalog) / DEFAULT_TOOL_CATALOG_NAME
    catalog = CatalogMem.load(catalog_path)
    tool = catalog.find(name=name)

    if len(tool) == 0:
        raise ValueError(f"No tool {name} in the catalog!")

    verify_provider_model_credentials(model)

    tool_info = tool[0].entry
    cf.settings.pretty_print_agent_events = False
    cf.settings.prefect_log_level = "CRITICAL"
    agent = cf.Agent(
        name="Test Agent",
        model=model,
        instructions=(
            "You are a helper who helps in testing the tool provided by user, follows objectives given carefully."
        ),
    )

    task1 = cf.Task(
        objective="Print all the inputs required by user to give for the tool and mention the user to provide inputs separated by commas",
        instructions="Take input from user as specified by the user and don't change anything in that or append anything to the user's input, keep it as it is. Don't prompt user multiple times, just take inputs and end the task.",
        context=dict(tool=tool_info),
        agents=[agent],
        interactive=True,
    )
    inputs = task1.run()

    task2 = cf.Task(
        objective="User has given the inputs for the tool separated by commas, execute the tool and return the results as returned by the tool executed properly.",
        context=dict(tool=tool_info, inputs=inputs),
        agents=[agent],
    )
    results = task2.run()

    click.secho("\nResults:", fg="green")
    click.echo(results)


def verify_provider_model_credentials(model: str):
    model_info = model.split("/")

    if len(model_info) != 2:
        raise ValueError(
            f"Invalid model {model} provided!\nProvide model name as {{provider}}/{{model_name}}.\nExample: openai/gpt-4o-mini"
        )

    provider = model_info[0]
    if provider not in ["openai", "azure-openai", "anthropic", "google", "groq"]:
        raise ValueError(
            f'Provided provider name {provider} is not supported!\nSupported providers are {", ".join(supported_providers)}.'
        )

    if os.getenv(f"{provider.upper()}_API_KEY") is None:
        raise ValueError(
            f"No API key provided for the chosen provider!\nPlease set the api key as {provider.upper()}_API_KEY"
        )
