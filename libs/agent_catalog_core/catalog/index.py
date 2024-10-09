import click
import fnmatch
import logging

from ..record.descriptor import RecordDescriptor
from .catalog.mem import CatalogMem
from .descriptor import CatalogDescriptor
from .directory import ScanDirectoryOpts
from .directory import scan_directory
from agent_catalog_core.defaults import DEFAULT_ITEM_DESCRIPTION_MAX_LEN
from agent_catalog_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agent_catalog_core.indexer import augment_descriptor
from agent_catalog_core.indexer import source_indexers
from agent_catalog_core.indexer import vectorize_descriptor

logger = logging.getLogger(__name__)

source_globs = list(source_indexers.keys())


def index_catalog(
    meta,
    version,
    get_path_version,
    kind,
    catalog_path,
    source_dirs,
    scan_directory_opts: ScanDirectoryOpts = None,
    printer=lambda x: None,
    progress=lambda x: x,
    max_errs=1,
):
    all_errs, next_catalog, uninitialized_items = index_catalog_start(
        meta,
        version,
        get_path_version,
        kind,
        catalog_path,
        source_dirs,
        scan_directory_opts=scan_directory_opts,
        printer=printer,
        progress=progress,
        max_errs=max_errs,
    )

    printer("Augmenting descriptor metadata.")
    logger.debug("Now augmenting descriptor metadata.")
    for descriptor in progress(uninitialized_items):
        if max_errs > 0 and len(all_errs) >= max_errs:
            break
        printer(f"- {descriptor.name}")
        logger.debug(f"Augmenting {descriptor.name}.")
        errs = augment_descriptor(descriptor)
        all_errs += errs or []

    if all_errs:
        logger.error("Encountered error(s) during augmenting: " + "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    import sentence_transformers

    embedding_model_obj = sentence_transformers.SentenceTransformer(
        meta["embedding_model"],
        tokenizer_kwargs={"clean_up_tokenization_spaces": True},
        cache_folder=DEFAULT_MODEL_CACHE_FOLDER,
        local_files_only=True,
    )

    printer("Generating embeddings for descriptors.")
    logger.debug("Now generating embeddings for descriptors.")
    for descriptor in progress(uninitialized_items):
        if max_errs > 0 and len(all_errs) >= max_errs:
            break
        printer(f"- {descriptor.name}")
        logger.debug(f"Generating embedding for {descriptor.name}.")
        errs = vectorize_descriptor(descriptor, embedding_model_obj)
        all_errs += errs or []

    if all_errs:
        logger.error("Encountered error(s) during embedding generation: " + "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    return next_catalog


def index_catalog_start(
    meta,
    version,
    get_path_version,
    kind,
    catalog_path,
    source_dirs,
    scan_directory_opts: ScanDirectoryOpts = None,
    printer=lambda x: None,
    progress=lambda x: x,
    max_errs=1,
):
    # TODO: We should use different source_indexers & source_globs based on the kind?

    # Load the old / previous local catalog if our catalog path exists.
    curr_catalog = (
        CatalogMem.load(catalog_path, embedding_model=meta["embedding_model"]) if catalog_path.exists() else None
    )

    source_files = []
    for source_dir in source_dirs:
        source_files += scan_directory(source_dir, source_globs, opts=scan_directory_opts)

    all_errs = []
    all_descriptors = []

    printer("Crawling source directories.")
    logger.debug("Now crawling source directories.")
    for source_file in progress(source_files):
        if 0 < max_errs <= len(all_errs):
            break

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(source_file.name, glob):
                printer(f"- {source_file.name}")
                logger.debug(f"Indexing file {source_file.name}.")

                # Flags to validate catalog item description
                is_description_empty = False
                is_description_length_valid = True

                errs, descriptors = indexer.start_descriptors(source_file, get_path_version)
                for descriptor in descriptors:
                    # Validate description lengths
                    if len(descriptor.description) == 0:
                        click.secho(f"WARNING: Catalog item {descriptor.name} has an empty description.", fg="yellow")
                        is_description_empty = True
                        break
                    if len(descriptor.description.split()) > DEFAULT_ITEM_DESCRIPTION_MAX_LEN:
                        click.secho(
                            f"WARNING: Catalog item {descriptor.name} has a description with token size more than the allowed limit.",
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
                        f"Catalog contains item(s) with description length more than the allowed limit of {DEFAULT_ITEM_DESCRIPTION_MAX_LEN}! Please provide a valid description and index again."
                    )
                all_errs += errs or []
                all_descriptors += descriptors or []
                break

    if all_errs:
        logger.error("Encountered error(s) while crawling source directories: " + "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    next_catalog = CatalogMem(
        catalog_descriptor=CatalogDescriptor(
            catalog_schema_version=meta["catalog_schema_version"],
            embedding_model=meta["embedding_model"],
            kind=kind,
            version=version,
            source_dirs=source_dirs,
            items=all_descriptors,
        )
    )

    uninitialized_items = init_from_catalog(next_catalog, curr_catalog)

    return all_errs, next_catalog, uninitialized_items


def init_from_catalog(working: CatalogMem, other: CatalogMem) -> list[RecordDescriptor]:
    """Initialize the items in self by copying over attributes from
    items found in other that have the exact same versions.

    Returns a list of uninitialized items."""

    uninitialized_items = []
    if other and other.catalog_descriptor:
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
