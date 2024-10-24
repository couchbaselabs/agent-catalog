from pydantic import BaseModel
from pydantic import model_validator
from typing_extensions import Optional


class SearchOptions(BaseModel):
    query: Optional[str] = ""
    name: Optional[str] = ""

    @model_validator(mode="after")
    @classmethod
    def check_one_field_populated(cls, values):
        query, item_name = values.query, values.name

        if (query and item_name) or (not query and not item_name):
            raise ValueError(
                "Exactly one of 'query' or 'name' must be populated. "
                "Please rerun your command with '--query' or '--name'."
            )

        return values
