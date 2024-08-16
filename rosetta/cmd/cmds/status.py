import flask
import click
import pathlib
import os

from rosetta.core.catalog.catalog_mem import CatalogMem
from rosetta.core.catalog.index import index_catalog_start
from rosetta.core.version import VersionDescriptor

from ..cmds.util import load_repository, init_local
from ..defaults import DEFAULT_SCAN_DIRECTORY_OPTS

blueprint = flask.Blueprint("status", __name__)


@blueprint.route("/status")
def route_status():
    kind = flask.request.args.get("kind", default="tool", type=str)
    include_dirty = (
            flask.request.args.get("include_dirty", default="true", type=str).lower() == "true"
    )

    return flask.jsonify(catalog_status(flask.current_app.config["ctx"], kind, include_dirty))


level_colors = {"good": "green", "warn": "yellow", "error": "red"}


def cmd_status(ctx, kind="tool", include_dirty=True):
    # TODO: Allow the kind to be '*' or None to show the
    # status on all the available kinds of catalogs.

    sections = catalog_status(ctx, kind, include_dirty=include_dirty)

    for section in sections:
        name, parts = section
        if name:
            click.echo("-------------")
            click.echo(name + ":")
            indent = "  "
        else:
            indent = ""

        for part in parts:
            level, msg = part
            if level in level_colors:
                click.secho(indent + msg, fg=level_colors[level])
            else:
                click.echo(indent + msg)


def catalog_status(ctx, kind, include_dirty=True):
    # TODO: One day implement status checks also against a CatalogDB
    # backend -- such as by validating DDL and schema versions,
    # looking for outdated items versus the local catalog, etc?

    # TODO: Validate schema versions -- if they're ahead, far behind, etc?

    catalog_path = pathlib.Path(ctx.catalog + "/" + kind + "-catalog.json")

    if not catalog_path.exists():
        return [
            (
                None,
                [
                    (
                        "error",
                        "ERROR: local catalog does not exist yet: please use the index command.",
                    )
                ],
            )
        ]

    sections = []

    catalog = CatalogMem().load(catalog_path)

    if include_dirty:
        repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
        if repo.is_dirty():
            sections.append(
                (
                    "repo commit",
                    [
                        (
                            "warn",
                            "repo is DIRTY: please use the index command to update the local catalog.",
                        )
                    ],
                )
            )
        else:
            version = VersionDescriptor(identifier=str(repo.head.commit))
            sections.append(
                (
                    "repo commit",
                    [(None, "repo is clean"), (None, f"repo version: {version}")],
                )
            )

        uninitialized_items = []

        if repo.is_dirty():
            section_parts = []

            meta = init_local(ctx, catalog.catalog_descriptor.embedding_model, read_only=True)

            version = VersionDescriptor(is_dirty=True)

            # Scan the same source_dirs that were used in the last "rosetta index".
            source_dirs = catalog.catalog_descriptor.source_dirs

            # Start a CatalogMem on-the-fly that incorporates the dirty
            # source file items which we'll use instead of the local catalog file.
            errs, catalog, uninitialized_items = index_catalog_start(
                meta,
                version,
                get_path_version,
                kind,
                catalog_path,
                source_dirs,
                scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                max_errs=0,
            )

            for err in errs:
                section_parts.append(("error", f"ERROR: {err}"))
            else:
                section_parts.append((None, "ok"))

            sections.append(("local scanning", section_parts))

        if uninitialized_items:
            section_parts = [(None, f"dirty items count: {len(uninitialized_items)}")]

            for x in uninitialized_items:
                section_parts.append(("None", f"- {x.source}: {x.name}"))

            sections.append(("local dirty items", section_parts))

    sections.append(
        (
            "local catalog info",
            [
                (None, f"path            : {catalog_path}"),
                (None, f"schema version  : {catalog.catalog_descriptor.catalog_schema_version}"),
                (None, f"kind of catalog : {catalog.catalog_descriptor.kind}"),
                (None, f"repo version    : {catalog.catalog_descriptor.version.identifier}"),
                (None, f"embedding model : {catalog.catalog_descriptor.embedding_model}"),
                (None, f"source dirs     : {catalog.catalog_descriptor.source_dirs}"),
                (None, f"number of items : {len(catalog.catalog_descriptor.items or [])}"),
            ],
        )
    )

    return sections
