import click
import couchbase.cluster
import datetime
import logging
import os
import pathlib
import textwrap
import tqdm
import typing

from ..models import Context
from ..models.find import SearchOptions
from .util import load_repository
from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog import CatalogDB
from agentc_core.catalog import CatalogMem
from agentc_core.catalog import SearchResult
from agentc_core.catalog import __version__ as CATALOG_SCHEMA_VERSION
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.catalog.version import lib_version
from agentc_core.defaults import DEFAULT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_MAX_ERRS
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.embedding.embedding import EmbeddingModel
from agentc_core.provider.refiner import ClosestClusterRefiner
from agentc_core.version import VersionDescriptor

refiners = {
    "ClosestCluster": ClosestClusterRefiner,
    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}

logger = logging.getLogger(__name__)


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
    catalog_id: str = None,
    cluster: couchbase.cluster.Cluster = None,
    embedding_model_name: str = None,
):
    # TODO: One day, also handle DBCatalogRef?
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: Possible security issue -- need to check kind is an allowed value?

    # TODO (GLENN): We should probably push this into agentc_core/catalog .
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
    _, get_path_version = load_repository(pathlib.Path(os.getcwd()))
    if bucket is not None and cluster is not None:
        embedding_model = EmbeddingModel(
            embedding_model_name=embedding_model_name,
            catalog_path=pathlib.Path(ctx.catalog),
            cb_bucket=bucket,
            cb_cluster=cluster,
        )
        catalog = CatalogDB(
            cluster=cluster,
            bucket=bucket,
            kind=kind,
            embedding_model=embedding_model,
            latest_version=get_path_version(pathlib.Path(os.getcwd())),
        )
        click.secho("Searching db...")

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
    # Local catalog find
    else:
        catalog_path = pathlib.Path(ctx.catalog) / (kind + DEFAULT_CATALOG_NAME)
        embedding_model = EmbeddingModel(
            embedding_model_name=embedding_model_name,
            catalog_path=pathlib.Path(ctx.catalog),
        )
        catalog = CatalogMem(catalog_path=catalog_path, embedding_model=embedding_model)

        if include_dirty:
            repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
            if repo and repo.is_dirty():
                # The repo and any dirty files do not have real commit id's, so use "DIRTY".
                version = VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

                # Scan the same source_dirs that were used in the last "agentc index".
                source_dirs = catalog.catalog_descriptor.source_dirs

                # Create a CatalogMem on-the-fly that incorporates the dirty
                # source file items which we'll use instead of the local catalog file.
                meta_version = MetaVersion(schema_version=CATALOG_SCHEMA_VERSION, library_version=lib_version())
                catalog = index_catalog(
                    embedding_model,
                    meta_version,
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
            for x in catalog.find(query, limit=limit, annotations=annotations_predicate, snapshot=catalog_id, name=name)
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
