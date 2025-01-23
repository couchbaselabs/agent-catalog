import typing

from ..models import Context
from .util import init_local_activity
from .util import init_local_catalog

func_mappings = {"local": {"catalog": init_local_catalog, "auditor": init_local_activity}}


def cmd_init(
    ctx: Context,
    catalog_type: typing.List[typing.Literal["catalog", "auditor"]],
    type_metadata: typing.List[typing.Literal["catalog", "auditor"]],
):
    if ctx is None:
        ctx = Context()

    for catalog in catalog_type:
        for init_type in type_metadata:
            func_mappings[catalog][init_type](ctx)
