import datetime
import json
import os

from pathlib import Path
from pydantic import BaseModel
from pydantic import field_validator
from pydantic_core.core_schema import ValidationInfo
from typing import Optional
from urllib.parse import urlparse


class Keyspace(BaseModel):
    """Pydantic model to capture keyspace"""

    bucket: str
    scope: str


class CouchbaseConnect(BaseModel):
    """Pydantic model to capture couchbase connection details"""

    connection_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    certificate_path: Optional[str] = None

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
        if parsed_url.scheme not in ["couchbase", "couchbases"] or parsed_url.netloc == "":
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

    @field_validator("certificate_path")
    @classmethod
    def certificate_path_must_be_valid_if_not_none(cls, path: str, info: ValidationInfo) -> Optional[str]:
        conn_url = info.data["connection_url"]
        if conn_url is not None and "couchbases" in conn_url:
            if path is None:
                raise ValueError(
                    "Could not find the environment variable $AGENT_CATALOG_CONN_ROOT_CERT_PATH!\n"
                    "Please run 'export AGENT_CATALOG_CONN_ROOT_CERT_PATH=...' or add "
                    "$AGENT_CATALOG_CONN_ROOT_CERT_PATH to your .env file and try again."
                )
            elif not os.path.exists(path):
                raise ValueError(
                    "Value provided for variable $AGENT_CATALOG_CONN_ROOT_CERT_PATH does not exist in your file system!\n"
                )
            elif not os.path.isfile(path):
                raise ValueError(
                    "Value provided for variable $AGENT_CATALOG_CONN_ROOT_CERT_PATH is not a valid path to the cluster's root certificate file!\n"
                )

            return path

        return None


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
