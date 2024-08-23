import fnmatch
import logging

from ..tool.indexer import augment_descriptor
from ..tool.indexer import source_indexers
from ..tool.indexer import vectorize_descriptor
from .catalog.mem import CatalogMem
from .descriptor import CatalogDescriptor
from .directory import ScanDirectoryOpts
from .directory import scan_directory

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
        meta["embedding_model"], tokenizer_kwargs={"clean_up_tokenization_spaces": True}
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
    curr_catalog = CatalogMem.load(catalog_path) if catalog_path.exists() else None

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
                errs, descriptors = indexer.start_descriptors(source_file, get_path_version)
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

    uninitialized_items = next_catalog.init_from(curr_catalog)

    return all_errs, next_catalog, uninitialized_items
