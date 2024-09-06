import click
import couchbase.cluster
import logging
import os
import pathlib
import textwrap
import tqdm
import typing

from ..defaults import DEFAULT_CATALOG_NAME
from ..defaults import DEFAULT_MAX_ERRS
from ..defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from ..models import Context
from .util import init_local
from .util import load_repository
from rosetta_cmd.models.find import SearchOptions
from rosetta_core.annotation import AnnotationPredicate
from rosetta_core.catalog import CatalogDB
from rosetta_core.catalog import CatalogMem
from rosetta_core.catalog import SearchResult
from rosetta_core.catalog.index import index_catalog
from rosetta_core.provider.refiner import ClosestClusterRefiner
from rosetta_core.version import VersionDescriptor

refiners = {
    "ClosestCluster": ClosestClusterRefiner,
    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}

logger = logging.getLogger(__name__)


# TODO (GLENN): Use an enum for kind instead of a string
# TODO (GLENN): Add support for name = ...
def cmd_find(
    ctx: Context,
    query: str = None,
    name: str = None,
    bucket: str = None,
    kind: typing.Literal["tool", "prompt"] = "tool",
    limit: int = 1,
    include_dirty: bool = True,
    refiner: str = None,
    annotations: str = None,
    cluster: couchbase.cluster.Cluster = None,
    embedding_model: str = None,
):
    # TODO: One day, also handle DBCatalogRef?
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: Possible security issue -- need to check kind is an allowed value?

    # TODO (GLENN): We should probably push this into core/catalog .
    # Validate that only query or only name is specified (error will be bubbled up).
    search_opt = SearchOptions(query=query, name=name)
    query = search_opt.query
    name = search_opt.name

    if refiner == "None":
        refiner = None
    if refiner is not None and refiner not in refiners:
        valid_refiners = list(refiners.keys())
        valid_refiners.sort()
        raise ValueError(f"ERROR: unknown refiner, valid refiners: {valid_refiners}")

    # DB level find
    if bucket is not None and cluster is not None:
        meta = init_local(ctx, embedding_model)
        catalog = CatalogDB(cluster=cluster, bucket=bucket, kind=kind, meta=meta)
        click.secho("Searching db...")

        annotations_predicate = AnnotationPredicate(annotations) if annotations is not None else None
        search_results = [
            SearchResult(entry=x.entry, delta=x.delta)
            for x in catalog.find(
                query=query,
                name=name,
                limit=limit,
                annotations=annotations_predicate,
            )
        ]
    # Local catalog find
    else:
        catalog_path = pathlib.Path(ctx.catalog) / (kind + DEFAULT_CATALOG_NAME)

        catalog = CatalogMem().load(catalog_path)

        if include_dirty:
            repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
            if repo and repo.is_dirty():
                meta = init_local(ctx, catalog.catalog_descriptor.embedding_model, read_only=True)

                # The repo and any dirty files do not have real commit id's, so use "DIRTY".
                version = VersionDescriptor(is_dirty=True)

                # Scan the same source_dirs that were used in the last "rosetta index".
                source_dirs = catalog.catalog_descriptor.source_dirs

                # Create a CatalogMem on-the-fly that incorporates the dirty
                # source file items which we'll use instead of the local catalog file.
                catalog = index_catalog(
                    meta,
                    version,
                    get_path_version,
                    kind,
                    catalog_path,
                    source_dirs,
                    scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                    printer=logger.debug if not ctx.verbose else click.echo,
                    progress=(lambda a: a) if not ctx.verbose else tqdm.tqdm,
                    max_errs=DEFAULT_MAX_ERRS,
                )

        # Query the catalog for a list of results.
        annotations_predicate = AnnotationPredicate(annotations) if annotations is not None else None
        search_results = [
            SearchResult(entry=x.entry, delta=x.delta)
            for x in catalog.find(query, limit=limit, annotations=annotations_predicate, name=name)
        ]

    if refiner is not None:
        search_results = refiners[refiner]()(search_results)
    click.secho(f"{len(search_results)} result(s) returned from the catalog.", bold=True, bg="green")
    if ctx.verbose:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", bold=True)
            click.echo(textwrap.indent(str(result.entry), "  "))
    else:
        for i, result in enumerate(search_results):
            click.secho(f"  {i + 1}. (delta = {result.delta}, higher is better): ", nl=False, bold=True)
            click.echo(str(result.entry.identifier))
