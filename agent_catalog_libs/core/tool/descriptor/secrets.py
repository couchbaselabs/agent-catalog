import pydantic


# TODO (GLENN): Add more types of secrets below.
class CouchbaseSecrets(pydantic.BaseModel):
    class Couchbase(pydantic.BaseModel):
        conn_string: str
        username: str
        password: str

    couchbase: Couchbase
