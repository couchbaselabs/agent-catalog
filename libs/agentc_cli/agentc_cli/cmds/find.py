import click
import logging
import pydantic
import textwrap
import typing

from .util import DASHES
from .util import KIND_COLORS
from .util import get_catalog
from .util import logging_command
from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog import SearchResult
from agentc_core.config import Config
from agentc_core.provider.refiner import ClosestClusterRefiner

refiners = {
    "ClosestCluster": ClosestClusterRefiner,
    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}

logger = logging.getLogger(__name__)


# TODO (GLENN): We should probably push this into agentc_core/catalog .
class SearchOptions(pydantic.BaseModel):
    query: typing.Optional[str] = ""
    name: typing.Optional[str] = ""

    @pydantic.model_validator(mode="after")
    @classmethod
    def check_one_field_populated(cls, values):
        query, item_name = values.query, values.name

        if (query and item_name) or (not query and not item_name):
            raise ValueError(
                "Exactly one of 'query' or 'name' must be populated. "
                "Please rerun your command with '--query' or '--name'."
            )

        return values


@logging_command(logger)
def cmd_find(
    cfg: Config = None,
    *,
    kind: typing.Literal["tool", "model-input"],
    with_db: bool,
    with_local: bool,
    query: str = None,
    name: str = None,
    limit: int = 1,
    include_dirty: bool = True,
    refiner: str = None,
    annotations: str = None,
    catalog_id: str = None,
):
    if cfg is None:
        cfg = Config()

    # Validate that only query or only name is specified (error will be bubbled up).
    search_opt = SearchOptions(query=query, name=name)
    query, name = search_opt.query, search_opt.name
    click.secho(DASHES, fg=KIND_COLORS[kind])
    click.secho(kind.upper(), bold=True, fg=KIND_COLORS[kind])
    click.secho(DASHES, fg=KIND_COLORS[kind])

    # Check if a refiner is specified.
    if refiner == "None":
        refiner = None
    if refiner is not None and refiner not in refiners:
        valid_refiners = list(refiners.keys())
        valid_refiners.sort()
        raise ValueError(f"Unknown refiner specified. Valid refiners are: {valid_refiners}")

    # Determine what type of catalog we want.
    if with_local and with_db:
        force = "chain"
    elif with_db:
        force = "db"
    elif with_local:
        force = "local"
    else:
        raise ValueError("Either local FS or DB catalog must be specified!")

    # Execute the find on our catalog.
    catalog = get_catalog(cfg=cfg, force=force, include_dirty=include_dirty, kind=kind)
    annotations_predicate = AnnotationPredicate(annotations) if annotations is not None else None
    search_results = [
        SearchResult(entry=x.entry, delta=x.delta)
        for x in catalog.find(
            query=query,
            name=name,
            limit=limit,
            snapshot=catalog_id,
            annotations=annotations_predicate,
        )
    ]

    if refiner is not None:
        search_results = refiners[refiner]()(search_results)
    click.secho(f"\n{len(search_results)} result(s) returned from the catalog.", bold=True, bg="green")
    if cfg.verbosity_level > 0:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", bold=True)
            click.echo(textwrap.indent(str(result.entry), "  "))
    else:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", nl=False, bold=True)
            click.echo(str(result.entry.identifier))
    click.secho(DASHES, fg=KIND_COLORS[kind])
