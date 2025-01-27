import pydantic
import typing


# TODO (GLENN): Add more types of secrets below.
class CouchbaseSecrets(pydantic.BaseModel):
    class Couchbase(pydantic.BaseModel):
        conn_string: str
        username: str
        password: str
        certificate: typing.Optional[str] = None

    couchbase: Couchbase
