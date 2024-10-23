import datetime
import json

from pathlib import Path
from pydantic import BaseModel
from pydantic import field_validator
from urllib.parse import urlparse


class Keyspace(BaseModel):
    """Pydantic model to capture keyspace"""

    bucket: str
    scope: str


class CouchbaseConnect(BaseModel):
    """Pydantic model to capture couchbase connection details"""

    connection_url: str | None
    username: str | None
    password: str | None
    host: str | None

    @field_validator("connection_url")
    @classmethod
    def must_follow_supported_url_pattern(cls, url: str) -> str:
        if url is None:
            raise ValueError(
                "Could not find CB_CONN_STRING in the environment variables file!\nAdd Couchbase connection string to environment variables file and try again."
            )
        url = url.strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme == "" or parsed_url.netloc == "":
            raise ValueError(
                "CB_CONN_STRING specified in the environment variables file doesn't follow the desired URL pattern!\nExamples of accepted format:\n\tcouchbase://localhost\n\tcouchbases://asdgfjgjkasdfghjkasdfghjk.cloud.couchbase.com"
            )

        return url

    @field_validator("username")
    @classmethod
    def username_must_not_be_empty(cls, uname: str) -> str:
        if uname is None:
            raise ValueError(
                "Could not find CB_USERNAME in the environment variables file!\nAdd Couchbase cluster access username to environment variables file and try again."
            )

        uname = uname.strip()
        if not uname:
            raise ValueError("CB_USERNAME environment variable should not be empty!")

        return uname

    @field_validator("password")
    @classmethod
    def password_must_not_be_empty(cls, pwd: str) -> str:
        if pwd is None:
            raise ValueError(
                "Could not find CB_PASSWORD in the environment variables file!\nAdd Couchbase cluster access password for the specified username to environment variables file and try again."
            )

        pwd = pwd.strip()
        if not pwd:
            raise ValueError("CB_PASSWORD environment variable should not be empty!")

        return pwd


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
