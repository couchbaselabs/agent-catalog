import pydantic
import typing


class CouchbaseSecrets(pydantic.BaseModel):
    class Couchbase(pydantic.BaseModel):
        conn_string: str
        username: str
        password: str
        certificate: typing.Optional[str] = None

    couchbase: Couchbase


class EmbeddingModelSecrets(pydantic.BaseModel):
    class OpenAI(pydantic.BaseModel):
        username: typing.Optional[str]
        password: typing.Optional[str]

    openai: OpenAI
