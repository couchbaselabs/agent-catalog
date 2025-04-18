import pydantic
import typing


class EmbeddingModel(pydantic.BaseModel):
    name: str = pydantic.Field(
        description="The name of the embedding model being used.",
        examples=["all-MiniLM-L12-v2", "intfloat/e5-mistral-7b-instruct"],
    )
    base_url: typing.Optional[str] = pydantic.Field(
        description="The base URL of the embedding model."
        "This field must be specified if using a non-SentenceTransformers-based model.",
        examples=["https://12fs345d.apps.cloud.couchbase.com"],
        default=None,
    )

    @property
    @pydantic.computed_field
    def kind(self) -> typing.Literal["sentence-transformers", "openai"]:
        return "sentence-transformers" if self.base_url is None else "openai"

    def __hash__(self):
        return self.name.__hash__()
