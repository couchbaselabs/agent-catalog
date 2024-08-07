import json
import pathlib
import click

from rosetta.core.catalog.ref import MemCatalogRef
from ..models.ctx.model import Context


def cmd_find(ctx: Context, query, kind="tool"):
    # TODO: One day, handle DBCatalogRef?

    # TODO: If DB is outdated and the local catalog has newer info,
    # then we need to consult the latest, local catalog / MemCatalogRef?

    # TODO: Optional, future flags might specify variations like --local-catalog-only
    # and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?

    # TODO: When refactoring is done, rename back to "tool_catalog.json" (with underscore)?

    # TODO: Possible security issue -- need to check kind is an allowed value?
    catalog_path = ctx.catalog + "/" + kind + "-catalog.json"

    c = MemCatalogRef().load(pathlib.Path(catalog_path))

    found_items = c.find(query)

    results = [x.tool_descriptor.model_copy()
               for x in found_items
               if not bool(x.deleted)]

    # TODO: Rerank the results?

    # Strip out the embedding vector as it's not usually useful and it's big.
    for x in results:
        # TODO: The embedding vector is too big to show by default, but perhaps
        # provide an option flag in case the user really wants to see it.
        x.embedding = None

    click.echo(json.dumps(results, sort_keys=True, indent=4))
