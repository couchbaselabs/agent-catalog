import click
import couchbase.cluster
import logging
import textwrap
import typing

from ..models import Context
from ..models.find import SearchOptions
from .util import DASHES
from .util import KIND_COLORS
from .util import get_catalog
from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog import SearchResult
from agentc_core.provider.refiner import ClosestClusterRefiner

refiners = {
    "ClosestCluster": ClosestClusterRefiner,
    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}

logger = logging.getLogger(__name__)


def cmd_find(
    ctx: Context = None,
    query: str = None,
    name: str = None,
    bucket: str = None,
    kind: typing.Literal["tool", "prompt"] = "tool",
    limit: int = 1,
    include_dirty: bool = True,
    refiner: str = None,
    annotations: str = None,
    catalog_id: str = None,
    cluster: couchbase.cluster.Cluster = None,
    force_db=False,
):
    if ctx is None:
        ctx = Context()

    # TODO: One day, also handle DBCatalogRef?
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: Possible security issue -- need to check kind is an allowed value?

    # TODO (GLENN): We should probably push this into agentc_core/catalog .
    # Validate that only query or only name is specified (error will be bubbled up).
    search_opt = SearchOptions(query=query, name=name)
    query, name = search_opt.query, search_opt.name
    click.secho(DASHES, fg=KIND_COLORS[kind])
    click.secho(kind.upper(), bold=True, fg=KIND_COLORS[kind])
    click.secho(DASHES, fg=KIND_COLORS[kind])

    if refiner == "None":
        refiner = None
    if refiner is not None and refiner not in refiners:
        valid_refiners = list(refiners.keys())
        valid_refiners.sort()
        raise ValueError(f"Unknown refiner specified. Valid refiners are: {valid_refiners}")

    # Execute the find on our catalog.
    catalog = get_catalog(ctx.catalog, bucket, cluster, force_db, include_dirty, kind)
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
    if ctx.verbose:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", bold=True)
            click.echo(textwrap.indent(str(result.entry), "  "))
    else:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", nl=False, bold=True)
            click.echo(str(result.entry.identifier))
    click.secho(DASHES, fg=KIND_COLORS[kind])
