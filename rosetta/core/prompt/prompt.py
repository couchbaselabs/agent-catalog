import pydantic
import typing


class Prompt(pydantic.BaseModel):
    prompt: str
    version: str
    embedding: list[float]
