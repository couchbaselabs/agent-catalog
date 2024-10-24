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
                "Could not find the environment variable $AGENT_CATALOG_CONN_STRING!\n"
                "Please run 'export AGENT_CATALOG_CONN_STRING=...' or add "
                "$AGENT_CATALOG_CONN_STRING to your .env file and try again."
            )
        url = url.strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme == "" or parsed_url.netloc == "":
            raise ValueError(
                "Malformed $AGENT_CATALOG_CONN_STRING recieved.\n"
                "Please edit your $AGENT_CATALOG_CONN_STRING and try again.\n"
                "Examples of accepted formats are:\n"
                "\tcouchbase://localhost\n"
                "\tcouchbases://my_capella.cloud.couchbase.com"
            )

        return url

    @field_validator("username")
    @classmethod
    def username_must_not_be_empty(cls, uname: str) -> str:
        if uname is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_USERNAME!\n"
                "Please run 'export AGENT_CATALOG_USERNAME=...' or add "
                "$AGENT_CATALOG_USERNAME to your .env file and try again."
            )

        uname = uname.strip()
        if not uname:
            raise ValueError(
                "The $AGENT_CATALOG_USERNAME environment variable should not be empty.\n"
                "Please set the $AGENT_CATALOG_USERNAME variable appropriately."
            )

        return uname

    @field_validator("password")
    @classmethod
    def password_must_not_be_empty(cls, pwd: str) -> str:
        if pwd is None:
            raise ValueError(
                "Could not find the environment variable $AGENT_CATALOG_PASSWORD!\n"
                "Please run 'export AGENT_CATALOG_PASSWORD=...' or add "
                "$AGENT_CATALOG_PASSWORD to your .env file and try again."
            )

        pwd = pwd.strip()
        if not pwd:
            raise ValueError(
                "The $AGENT_CATALOG_PASSWORD environment variable should not be empty.\n"
                "Please set the $AGENT_CATALOG_PASSWORD variable appropriately."
            )

        return pwd


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
