import typing

from ..models import Context
from .util import init_local_activity
from .util import init_local_catalog


def cmd_init(ctx: Context, type_metadata: typing.List[typing.Literal["index", "publish", "audit"]]):
    if ctx is None:
        ctx = Context()

    if "index" in type_metadata:
        init_local_catalog(ctx)

    if "audit" in type_metadata:
        init_local_activity(ctx)
