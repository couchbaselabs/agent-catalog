#
# The following file is a template for a Python tool.
#
from rosetta.core.tool import tool
from pydantic import BaseModel


# Although Python uses duck-typing, the specification of types greatly improves the response quality of LLMs.
# It is highly recommended that all tools specify the types of their bound functions using Pydantic or dataclasses.
class SalesModel(BaseModel):
    input_sources: list[str]
    sales_formula: str


# Only functions decorated with rosetta.core.tool.tool will be indexed.
# All other functions / module members will be ignored by the indexer.
@tool(infer_schema=True)
def compute_sales_for_this_week(sales_model: SalesModel) -> float:
    """ A description for the function bound to the tool. This is mandatory for tools. """

    # The implementation of the tool (given below) is *not* indexed.
    # The indexer only cares about the name, function signature, and description.
    return 1.0 * 0.99 + 2.00 % 6.0
