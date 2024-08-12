import pydantic
from rosetta.core.tool import tool


class TravelCost(pydantic.BaseModel):
    distance: float
    fuel_efficiency: float
    fuel_price: float
    total_cost: float


@tool(infer_schema=True)
def calculate_travel_costs(distance: float, fuel_efficiency: float, fuel_price: float) -> TravelCost:
    """ Calculate the travel costs based on distance, fuel efficiency, and fuel price. """
    return None
