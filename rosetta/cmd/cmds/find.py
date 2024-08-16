import tqdm
import jsbeautifier

from ...cmd.cmds.util import *
from ...core.catalog.index import index_catalog
from ...core.catalog.catalog_mem import CatalogMem
from ...core.catalog.catalog_base import SearchResult
from ...core.provider.refiner import ClosestClusterRefiner
from ...core.version import VersionDescriptor
from ..models.ctx.model import Context

refiners = {
    "ClosestCluster": ClosestClusterRefiner,

    # TODO: One day allow for custom refiners at runtime where
    # we dynamically import a user's custom module/function?
}

beautify_opts = jsbeautifier.BeautifierOptions(options={
    "indent_size": 2,
    "indent_char": " ",
    "max_preserve_newlines": -1,
    "preserve_newlines": False,
    "keep_array_indentation": False,
    "brace_style": "expand",
    "unescape_strings": False,
    "end_with_newline": False,
    "wrap_line_length": 0,
    "comma_first": False,
    "indent_empty_lines": False
})


def cmd_find(ctx: Context, query, kind="tool", limit=1, include_dirty=True, refiner=None, annotations=None):
    # TODO: One day, also handle DBCatalogRef?
    # TODO: If DB is outdated and the local catalog has newer info,
    #       then we need to consult the latest, local catalog / MemCatalogRef?
    # TODO: Optional, future flags might specify variations like --local-catalog-only
    #       and/or --db-catalog-only, and/or both, via chaining multiple CatalogRef's?
    # TODO: When refactoring is done, rename back to "tool_catalog.json" (with underscore)?
    # TODO: Possible security issue -- need to check kind is an allowed value?

    if refiner == "None":
        refiner = None
    if refiner is not None and refiner not in refiners:
        valid_refiners = list(refiners.keys())
        valid_refiners.sort()
        raise ValueError(f"ERROR: unknown refiner, valid refiners: {valid_refiners}")

    catalog_path = pathlib.Path(ctx.catalog) / (kind + "-catalog.json")

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
            catalog = index_catalog(meta, version, get_path_version,
                                    kind, catalog_path, source_dirs,
                                    scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                                    printer=click.echo,
                                    progress=tqdm.tqdm, max_errs=DEFAULT_MAX_ERRS)

    # Transform our list of annotations into a single dictionary.
    annotations_dict = dict()
    for annotation in annotations:
        if '=' not in annotation:
            raise ValueError('Invalid format for annotation. Use "[key]=[value]".')
        else:
            k, v = annotation.split('=', maxsplit=1)
            annotations_dict[k] = v

    # Query the catalog for a list of results.
    search_results = [
        SearchResult(entry=x.entry, delta=x.delta) for x in
        catalog.find(query, limit=limit, annotations=annotations_dict)
    ]
    if refiner is not None:
        search_results = refiners[refiner]()(search_results)
    for i, result in enumerate(search_results):
        pretty_json = jsbeautifier.beautify(
            result.entry.model_dump_json(exclude={'embedding'}),
            opts=beautify_opts
        )
        click.echo(f'#{i + 1} (delta = {result.delta}, higher is better): ', nl=False)
        click.echo(pretty_json)
