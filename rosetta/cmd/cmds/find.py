import json
import pathlib
import click

from rosetta.core.catalog.catalog_mem import CatalogMem
from ..models.ctx.model import Context


def cmd_find(ctx: Context, query, kind="tool", max=1):
    # TODO: One day, handle DBCatalogRef?

    # TODO: If the repo is dirty, load the dirty items into a
    # CatalogMem and setup a chain of catalogs to perform the find().

    # TODO: If DB is outdated and the local catalog has newer info,
    # then we need to consult the latest, local catalog / MemCatalogRef?

    # TODO: Optional, future flags might specify variations like --local-catalog-only
    # and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?

    # TODO: When refactoring is done, rename back to "tool_catalog.json" (with underscore)?

    # TODO: Perhaps users optionally want the deltas or similarity scores, too?

    # TODO: Possible security issue -- need to check kind is an allowed value?
    catalog_path = ctx.catalog + "/" + kind + "-catalog.json"

    c = CatalogMem().load(pathlib.Path(catalog_path))

    found_items = c.find(query, max=max)

    results = [x.record_descriptor.model_dump() for x in found_items]

    # TODO: Rerank the results?

    # Strip out the embedding vector as it's not usually useful and it's big.
    for x in results:
        # Convert pathlib.Path to str so json.dumps() works.
        if 'source' in x:
            x["source"] = str(x["source"])

        # TODO: The embedding vector is too big to show by default, but perhaps
        # provide an option flag in case the user really wants to see it.
        if 'embedding' in x:
            del x['embedding']

    click.echo(json.dumps(results, sort_keys=True, indent=4))
