import dataclasses
import fnmatch
import logging
import tqdm
import typing

from ..defaults import DEFAULT_ITEM_DESCRIPTION_MAX_LEN
from ..indexer import AllIndexers
from ..indexer import vectorize_descriptor
from ..learned.embedding import EmbeddingModel
from ..record.descriptor import RecordDescriptor
from .catalog.mem import CatalogMem
from .descriptor import CatalogDescriptor
from .directory import ScanDirectoryOpts
from .directory import scan_directory
from .version import catalog_schema_version_compare
from .version import lib_version_compare

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MetaVersion:
    schema_version: str
    library_version: str


def index_catalog(
    embedding_model: EmbeddingModel,
    meta_version: MetaVersion,
    catalog_version: str,
    get_path_version: typing.Callable[[str], str],
    kind: typing.Literal["tool", "prompt"],
    catalog_path,
    source_dirs,
    scan_directory_opts: ScanDirectoryOpts = None,
    printer: typing.Callable = lambda x, *args, **kwargs: print(x),
    print_progress: bool = True,
    max_errs=1,
):
    all_errs, next_catalog, uninitialized_items = index_catalog_start(
        embedding_model=embedding_model,
        meta_version=meta_version,
        catalog_version=catalog_version,
        get_path_version=get_path_version,
        kind=kind,
        catalog_path=catalog_path,
        source_dirs=source_dirs,
        scan_directory_opts=scan_directory_opts,
        printer=printer,
        print_progress=print_progress,
        max_errs=max_errs,
    )

    # For now, we do no augmentation so we'll comment this out.
    # printer("Augmenting descriptor metadata.")
    # logger.debug("Now augmenting descriptor metadata.")
    # for descriptor in progress(uninitialized_items):
    #     if 0 < max_errs <= len(all_errs):
    #         break
    #     printer(f"- {descriptor.name}")
    #     logger.debug(f"Augmenting {descriptor.name}.")
    #     errs = augment_descriptor(descriptor)
    #     all_errs += errs or []
    #
    # if all_errs:
    #     logger.error("Encountered error(s) during augmenting: " + "\n".join([str(e) for e in all_errs]))
    #     raise all_errs[0]

    logger.debug("Now generating embeddings for descriptors.")
    printer("\nGenerating embeddings:")
    item_iterator = tqdm.tqdm(uninitialized_items) if print_progress else uninitialized_items
    for descriptor in item_iterator:
        if 0 < max_errs <= len(all_errs):
            break
        if print_progress:
            item_iterator.set_description(f"{descriptor.name}")
        logger.debug(f"Generating embedding for {descriptor.name}.")
        errs = vectorize_descriptor(descriptor, embedding_model)
        all_errs += errs or []

    if all_errs:
        logger.error("Encountered error(s) during embedding generation: " + "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    return next_catalog


def index_catalog_start(
    embedding_model: EmbeddingModel,
    meta_version: MetaVersion,
    catalog_version: str,
    get_path_version: typing.Callable[[str], str],
    kind: typing.Literal["tool", "prompt"],
    catalog_path,
    source_dirs,
    scan_directory_opts: ScanDirectoryOpts = None,
    printer: typing.Callable = lambda x, *args, **kwargs: print(x),
    print_progress: bool = True,
    max_errs=1,
):
    # Load the old / previous local catalog if our catalog path exists.
    curr_catalog = (
        CatalogMem(catalog_path=catalog_path, embedding_model=embedding_model) if catalog_path.exists() else None
    )

    logger.debug(f"Now crawling source directories. [{','.join(d for d in source_dirs)}]")
    printer(f"Crawling {','.join(d for d in source_dirs)}:")
    source_files = list()
    if kind == "tool":
        source_globs = [i.glob_pattern for i in AllIndexers if all(k.is_tool() for k in i.kind)]
    elif kind == "prompt":
        source_globs = [i.glob_pattern for i in AllIndexers if all(k.is_prompt() for k in i.kind)]
    else:
        raise ValueError(f"Unknown kind: {kind}")
    for source_dir in source_dirs:
        source_files += scan_directory(source_dir, source_globs, opts=scan_directory_opts)
    all_errs = []
    all_descriptors = []
    source_iterable = tqdm.tqdm(source_files) if print_progress else source_files
    for source_file in source_iterable:
        if 0 < max_errs <= len(all_errs):
            break
        if print_progress:
            source_iterable.set_description(f"{source_file.name}")
        for indexer in AllIndexers:
            if fnmatch.fnmatch(source_file.name, str(indexer.glob_pattern)):
                logger.debug(f"Indexing file {source_file.name}.")

                # Flags to validate catalog item description
                is_description_empty = False
                is_description_length_valid = True

                errs, descriptors = indexer.start_descriptors(source_file, get_path_version)
                for descriptor in descriptors:
                    # Validate description lengths
                    if len(descriptor.description) == 0:
                        printer(f"WARNING: Catalog item {descriptor.name} has an empty description.", fg="yellow")
                        is_description_empty = True
                        break
                    if len(descriptor.description.split()) > DEFAULT_ITEM_DESCRIPTION_MAX_LEN:
                        printer(
                            f"WARNING: Catalog item {descriptor.name} has a description with token size more"
                            f" than the allowed limit.",
                            fg="yellow",
                        )
                        is_description_length_valid = False
                        break

                if is_description_empty:
                    raise ValueError(
                        "Catalog contains item(s) with empty description! Please provide a description and index again."
                    )
                if not is_description_length_valid:
                    raise ValueError(
                        f"Catalog contains item(s) with description length more than the allowed limit of "
                        f"{DEFAULT_ITEM_DESCRIPTION_MAX_LEN}! Please provide a valid description and index again."
                    )
                all_errs += errs or []
                all_descriptors += descriptors or []
                break

    if all_errs:
        logger.error("Encountered error(s) while crawling source directories: " + "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    next_catalog = CatalogMem(
        embedding_model=embedding_model,
        catalog_descriptor=CatalogDescriptor(
            schema_version=meta_version.schema_version,
            library_version=meta_version.library_version,
            version=catalog_version,
            embedding_model=embedding_model.name,
            kind=kind,
            source_dirs=source_dirs,
            items=all_descriptors,
        ),
    )

    uninitialized_items = init_from_catalog(next_catalog, curr_catalog)
    return all_errs, next_catalog, uninitialized_items


def init_from_catalog(working: CatalogMem, other: CatalogMem) -> list[RecordDescriptor]:
    """Initialize the items in self by copying over attributes from
    items found in other that have the exact same versions.

    Returns a list of uninitialized items."""

    uninitialized_items = []
    if other and other.catalog_descriptor:
        # Perform catalog schema checking + library version checking here.
        schema_version_s1 = working.catalog_descriptor.schema_version
        schema_version_s2 = other.catalog_descriptor.schema_version
        if catalog_schema_version_compare(schema_version_s1, schema_version_s2) > 0:
            # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
            raise ValueError("Version of local catalog's catalog_schema_version is ahead.")

        lib_version_s1 = working.catalog_descriptor.library_version
        lib_version_s2 = other.catalog_descriptor.library_version
        if lib_version_compare(lib_version_s1, lib_version_s2) > 0:
            # TODO: Perhaps we're too strict here and should allow micro versions that get ahead.
            raise ValueError("Version of local catalog's lib_version is ahead.")

        # A lookup dict of items keyed by "source:name".
        other_items = {str(o.source) + ":" + o.name: o for o in other.catalog_descriptor.items or []}

        for s in working.catalog_descriptor.items:
            o = other_items.get(str(s.source) + ":" + s.name)
            if o and not s.version.is_dirty and o.version.identifier == s.version.identifier:
                # The prev item and self item have the same version IDs,
                # so copy the prev item contents into the self item.
                for k, v in o.model_dump().items():
                    setattr(s, k, v)
            else:
                uninitialized_items.append(s)
    else:
        uninitialized_items += working.catalog_descriptor.items

    return uninitialized_items
