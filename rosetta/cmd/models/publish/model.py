from pydantic import BaseModel


class Keyspace(BaseModel):
    """Pydantic model to capture keyspace"""

    bucket: str
    scope: str


class CouchbaseConnect(BaseModel):
    """Pydantic model to capture couchbase connection details"""

    connection_url: str = "couchbase://localhost"
    username: str = "Administrator"
    password: str = "password"
