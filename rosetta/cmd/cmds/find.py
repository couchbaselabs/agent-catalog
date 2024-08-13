import tqdm

from rosetta.cmd.cmds.util import *
from rosetta.core.catalog.index import index_catalog
from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.core.provider.refiner import ClosestClusterRefiner
from rosetta.core.provider.refiner import EntryWithDelta
from ..models.ctx.model import Context


def NoneRefiner():
    return lambda results: results


refiners = {
    "None": NoneRefiner,
    "ClosestCluster": ClosestClusterRefiner,

    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}


def cmd_find(ctx: Context, query, kind="tool", top_k=3, include_dirty=True, refiner="ClosestCluster"):
    # TODO: One day, also handle DBCatalogRef?
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: When refactoring is done, rename back to "tool_catalog.json" (with underscore)?
    # TODO: Possible security issue -- need to check kind is an allowed value?

    if not any(r.lower() == refiner.lower() for r in refiners):
        valid_refiners = list(refiners.keys())
        valid_refiners.sort()
        raise ValueError(f"ERROR: unknown refiner, valid refiners: {valid_refiners}")

    catalog_path = pathlib.Path(ctx.catalog) / (kind + "-catalog.json")

    catalog = CatalogMem().load(catalog_path)

    if include_dirty:
        repo, repo_commit_id_for_path = repo_load(pathlib.Path(os.getcwd()))
        if repo and repo.is_dirty():
            meta = init_local(ctx, catalog.catalog_descriptor.embedding_model, read_only=True)

            # The repo and any dirty files do not have real commit id's, so use "DIRTY".
            repo_commit_id = REPO_DIRTY

            # Scan the same source_dirs that were used in the last "rosetta index".
            source_dirs = catalog.catalog_descriptor.source_dirs

            # Create a CatalogMem on-the-fly that incorporates the dirty
            # source file items which we'll use instead of the local catalog file.
            catalog = index_catalog(meta, repo_commit_id, repo_commit_id_for_path,
                                    kind, catalog_path, source_dirs,
                                    scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                                    progress=tqdm.tqdm, max_errs=DEFAULT_MAX_ERRS)

    # Query the catalog for a list of results.
    search_results = [
        EntryWithDelta(entry=x.record_descriptor, delta=x.delta) for x in catalog.find(query, limit=top_k)
    ]

    refiner_fn = refiners[refiner]()
    for i, result in enumerate(refiner_fn(search_results)):
        click.echo(f'#{i + 1} (delta = {result.delta}, higher is better): ', nl=False)
        click.echo(str(result.entry))
