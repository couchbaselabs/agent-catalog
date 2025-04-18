#
# The following file is a template for a Python tool.
#
from agentc.catalog import tool
from pydantic import BaseModel


# Although Python uses duck-typing, the specification of models greatly improves the response quality of LLMs.
# It is highly recommended that all tools specify the models of their bound functions using Pydantic or dataclasses.
class SalesModel(BaseModel):
    input_sources: list[str]
    sales_formula: str


# Only functions decorated with "tool" will be indexed.
# All other functions / module members will be ignored by the indexer.
@tool
def compute_sales_for_this_week(sales_model: SalesModel) -> float:
    """A description for the function bound to the tool. This is mandatory for tools."""

    return 1.0 * 0.99 + 2.00 % 6.0


# You can also specify the name and description of the tool explicitly, as well as any annotations you wish to attach.
@tool(name="compute_sales_for_the_month", annotations={"type": "sales"})
def compute_sales_for_the_month(sales_model: SalesModel) -> float:
    """A description for the function bound to the tool. This is mandatory for tools."""

    return 1.0 * 0.99 + 2.00 % 6.0
