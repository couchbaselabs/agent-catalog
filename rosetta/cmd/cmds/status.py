import pathlib

from rosetta.cmd.cmds.util import *
from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.core.catalog.index import index_catalog_start


def cmd_status(ctx, kind="tool"):
    # TODO: Implement status checks also against a CatalogDB backend --
    # such as by validating DDL and schema versions,
    # looking for outdated items versus the local catalog, etc?

    # TODO: Validate schema versions -- if they're ahead, far behind, etc?

    # TODO: Allow the kind to be '*' or None to show status
    # on all the available kinds of catalogs.

    repo, repo_commit_id_for_path = repo_load(pathlib.Path(os.getcwd()))
    if repo.is_dirty():
        repo_commit_id = REPO_DIRTY
        click.secho("repo is DIRTY -- use 'rosetta index' to update the local catalog.", fg='red')
    else:
        repo_commit_id = repo_commit_id_str(repo.head.commit)
        click.echo(f"repo commit id: {repo_commit_id}")

    catalog_path = pathlib.Path(ctx.catalog + "/" + kind + "-catalog.json")
    if not catalog_path.exists():
        click.secho("local catalog does not exist yet -- use the index command.", fg='red')
        return

    catalog = CatalogMem().load(catalog_path)

    uninitialized_items = []

    if repo.is_dirty():
        click.echo("-------------")
        click.echo("scanning dirty items...")

        meta = init_local(ctx, catalog.catalog_descriptor.embedding_model, read_only=True)

        repo_commit_id = REPO_DIRTY

        # Scan the same source_dirs that were used in the last "rosetta index".
        source_dirs = catalog.catalog_descriptor.source_dirs

        # Start a CatalogMem on-the-fly that incorporates the dirty
        # source file items which we'll use instead of the local catalog file.
        all_errs, catalog, uninitialized_items = index_catalog_start(
            meta, repo_commit_id, repo_commit_id_for_path,
            kind, catalog_path, source_dirs,
            scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
            max_errs=999999)

        for err in all_errs:
            click.secho(f"ERROR: {err}", fg="red")

    if uninitialized_items:
        click.echo("-------------")
        click.echo(f"dirty items count: {len(uninitialized_items)}")
        click.echo("dirty items:")
        for x in uninitialized_items:
            click.echo(f"  - {x.source}: {x.name}")

    click.echo("-------------")
    click.echo("catalog info:")
    click.echo(f"  path            : {catalog_path}")
    click.echo(f"  schema version  : {catalog.catalog_descriptor.catalog_schema_version}")
    click.echo(f"  kind of catalog : {catalog.catalog_descriptor.kind}")
    click.echo(f"  number of items : {len(catalog.catalog_descriptor.items or [])}")
    click.echo(f"  embedding model : {catalog.catalog_descriptor.embedding_model}")
    click.echo(f"  source dirs     : {catalog.catalog_descriptor.source_dirs}")
