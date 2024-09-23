import datetime
import json

from pathlib import Path
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


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
