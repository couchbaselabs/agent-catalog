import datetime
import json

from pathlib import Path


class CustomPublishEncoder(json.JSONEncoder):
    """Custom Json encoder for serialising/de-serialising catalog items while inserting into the DB."""

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
