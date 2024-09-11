from pydantic import BaseModel
from pydantic import model_validator


class SearchOptions(BaseModel):
    query: str = ""
    name: str = ""

    @model_validator(mode="after")
    @classmethod
    def check_one_field_populated(cls, values):
        query, item_name = values.query, values.name

        if (query and item_name) or (not query and not item_name):
            raise ValueError("Exactly one of 'query' or 'name' must be populated.")

        return values
