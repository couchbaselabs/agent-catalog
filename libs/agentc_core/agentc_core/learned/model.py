import pydantic
import typing


class EmbeddingModel(pydantic.BaseModel):
    kind: typing.Literal["sentence-transformers", "openai"] = pydantic.Field(
        description="The type of embedding model being used."
    )
    name: str = pydantic.Field(
        description="The name of the embedding model being used.",
        examples=["all-MiniLM-L12-v2", "https://12fs345d.apps.cloud.couchbase.com"],
    )
    base_url: typing.Optional[str] = pydantic.Field(
        description="The base URL of the embedding model."
        "This field must be specified is using a non-SentenceTransformers-based model.",
        examples=["https://12fs345d.apps.cloud.couchbase.com"],
    )
