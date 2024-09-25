import click
import datetime
import importlib.util
import os
import pathlib
import typing

from ..cmds.util import init_local
from ..cmds.util import load_repository
from ..defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from ..models.context import Context
from rosetta_core.catalog import CatalogMem
from rosetta_core.catalog.index import index_catalog_start
from rosetta_core.version import VersionDescriptor

level_colors = {"good": "green", "warn": "yellow", "error": "red"}
kind_colors = {"tool": "bright_magenta", "prompt": "blue"}


def cmd_status(ctx: Context, kind: typing.Literal["all", "tool", "prompt"] = "all", include_dirty: bool = True):
    catalog_kinds = ["tool", "prompt"] if kind == "all" else [kind]

    for catalog_kind in catalog_kinds:
        sections = catalog_status(ctx, catalog_kind, include_dirty=include_dirty)

        click.secho("-----------------------------------------------------------------", fg=kind_colors[catalog_kind])
        click.secho(catalog_kind.upper(), fg=kind_colors[catalog_kind])

        for section in sections:
            name, parts = section
            if name:
                click.secho("-------------", fg=kind_colors[catalog_kind])
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
        click.secho("-----------------------------------------------------------------", fg=kind_colors[catalog_kind])


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
                        f"ERROR: local catalog of kind {kind} does not exist yet: please use the index command by specifying the kind.",
                    )
                ],
            )
        ]

    sections = []

    catalog = CatalogMem.load(catalog_path)

    if include_dirty:
        repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
        if repo.is_dirty():
            sections.append(
                (
                    "repo commit",
                    [
                        (
                            "warn",
                            f"repo of kind {kind} is DIRTY: please use the index command to update the local catalog.",
                        )
                    ],
                )
            )
        else:
            version = VersionDescriptor(
                identifier=str(repo.head.commit), timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
            )
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

            version = VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

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


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("status", __name__)

    @blueprint.route("/status")
    def route_status():
        kind = flask.request.args.get("kind", default="tool", type=str)
        include_dirty = flask.request.args.get("include_dirty", default="true", type=str).lower() == "true"

        return flask.jsonify(catalog_status(flask.current_app.config["ctx"], kind, include_dirty))