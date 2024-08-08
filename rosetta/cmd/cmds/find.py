import pathlib

import click
import tqdm

from rosetta.cmd.cmds.util import *
from rosetta.core.catalog.index import index_catalog
from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.core.tool.reranker import ClosestClusterReranker
from rosetta.core.tool.reranker import ToolWithDelta
from ..models.ctx.model import Context


def cmd_find(ctx: Context, query, kind="tool", top_k=3):
    # TODO: One day, handle DBCatalogRef?
    # TODO: If the repo is dirty, load the dirty items into a
    #       CatalogMem and setup a chain of catalogs to perform the find().
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: When refactoring is done, rename back to "tool_catalog.json" (with underscore)?
    # TODO: Perhaps users optionally want the deltas or similarity scores, too?
    # TODO: Possible security issue -- need to check kind is an allowed value?
    catalog_path = pathlib.Path(ctx.catalog + "/" + kind + "-catalog.json")

    # Query our catalog for a list of results.
    catalog = CatalogMem().load(catalog_path)

    repo = repo_load(pathlib.Path(os.getcwd()))

    if repo and repo.is_dirty():
        # Create a CatalogMem that also includes the dirty items.

        meta = init_local(ctx, catalog.catalog_descriptor.embedding_model, read_only=True)

        # A dirty file and/or repo does not have a real commit id, so we use "DIRTY".
        repo_commit_id = "DIRTY"

        def get_repo_commit_id(path: pathlib.Path) -> str:
            if repo.is_dirty(path=path.absolute()):
                return "DIRTY"

            commits = list(repo.iter_commits(paths=path.absolute(), max_count=1))
            if not commits or len(commits) <= 0:
                return "DIRTY"

            return commit_str(commits[0])

        source_dirs = catalog.catalog_descriptor.source_dirs

        catalog = index_catalog(meta, repo_commit_id, get_repo_commit_id,
                                kind, catalog_path, source_dirs,
                                progress=tqdm.tqdm, max_errs=MAX_ERRS)

    search_results = [
        ToolWithDelta(tool=x.record_descriptor, delta=x.delta) for x in catalog.find(query, max=top_k)
    ]

    # TODO (GLENN): If / when different rerankers are implemented, specify them above.
    reranker = ClosestClusterReranker()
    for i, result in enumerate(reranker(search_results)):
        click.echo(f'#{i + 1} (delta = {result.delta}, higher is better): ', nl=False)
        click.echo(result.tool.pretty_json)
