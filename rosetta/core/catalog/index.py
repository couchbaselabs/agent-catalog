import fnmatch

from rosetta.core.tool.indexer import source_indexers, augment_descriptor, vectorize_descriptor

from .directory import scan_directory, ScanDirectoryOpts
from .descriptor import CatalogDescriptor
from .catalog_mem import CatalogMem


source_globs = list(source_indexers.keys())


def index_catalog(meta, repo_commit_id, repo_commit_id_for_path,
                  kind, catalog_path, source_dirs,
                  scan_directory_opts: ScanDirectoryOpts = None,
                  progress=lambda x: x,
                  max_errs=1):
    all_errs, next_catalog, uninitialized_items = index_catalog_start(
        meta, repo_commit_id, repo_commit_id_for_path,
        kind, catalog_path, source_dirs,
        scan_directory_opts=scan_directory_opts,
        progress=progress, max_errs=max_errs)

    print("==================\naugmenting...")

    for descriptor in progress(uninitialized_items):
        if len(all_errs) > max_errs:
            break

        print(descriptor.name)

        errs = augment_descriptor(descriptor)

        all_errs += errs or []

    if all_errs:
        print("ERROR: during augmenting", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    print("==================\nvectorizing...")

    import sentence_transformers

    embedding_model_obj = sentence_transformers.SentenceTransformer(meta["embedding_model"])

    for descriptor in progress(uninitialized_items):
        if len(all_errs) > max_errs:
            break

        print(descriptor.name)

        errs = vectorize_descriptor(descriptor, embedding_model_obj)

        all_errs += errs or []

    if all_errs:
        print("ERROR: during vectorizing", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    return next_catalog


def index_catalog_start(meta, repo_commit_id, repo_commit_id_for_path,
                        kind, catalog_path, source_dirs,
                        scan_directory_opts: ScanDirectoryOpts = None,
                        progress=lambda x: x,
                        max_errs=1):
    # TODO: We should use different source_indexers & source_globs based on the kind?

    if catalog_path.exists():
        # Load the old / previous local catalog.
        curr_catalog = CatalogMem().load(catalog_path)
    else:
        # An empty CatalogMem with no items represents an initial catalog state.
        curr_catalog = CatalogMem()
        curr_catalog.catalog_descriptor = CatalogDescriptor(
            catalog_schema_version=meta["catalog_schema_version"],
            kind=kind,
            embedding_model=meta["embedding_model"],
            repo_commit_id="",
            items=[])

    source_files = []
    for source_dir in source_dirs:
        source_files += scan_directory(source_dir, source_globs, opts=scan_directory_opts)

    all_errs = []
    all_descriptors = []
    for source_file in progress(source_files):
        if len(all_errs) > max_errs:
            break

        for glob, indexer in source_indexers.items():
            if fnmatch.fnmatch(source_file.name, glob):
                errs, descriptors = indexer.start_descriptors(source_file, repo_commit_id_for_path)
                all_errs += errs or []
                all_descriptors += descriptors or []
                break

    if all_errs:
        print("ERROR: during start_descriptors", "\n".join([str(e) for e in all_errs]))
        raise all_errs[0]

    next_catalog = CatalogMem(catalog_descriptor=CatalogDescriptor(
        catalog_schema_version=meta["catalog_schema_version"],
        embedding_model=meta["embedding_model"],
        kind=kind,
        repo_commit_id=repo_commit_id,
        source_dirs=source_dirs,
        items=all_descriptors
    ))

    uninitialized_items = next_catalog.init_from(curr_catalog)

    return all_errs, next_catalog, uninitialized_items
