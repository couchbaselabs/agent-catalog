import click
import datetime
import git
import importlib.util
import logging
import os
import pathlib
import typing

from ..cmds.util import DASHES
from ..cmds.util import KIND_COLORS
from ..cmds.util import LEVEL_COLORS
from ..cmds.util import load_repository
from ..models.context import Context
from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog_start
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.util.query import execute_query
from agentc_core.version import VersionDescriptor
from couchbase.exceptions import KeyspaceNotFoundException
from couchbase.exceptions import ScopeNotFoundException

logger = logging.getLogger(__name__)


def cmd_status(
    ctx: Context,
    kind: list[typing.Literal["tool", "prompt"]],
    include_dirty: bool = True,
    status_db: bool = False,
    bucket: str = None,
    cluster: any = None,
    compare: bool = False,
):
    for catalog_kind in kind:
        if status_db:
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
            click.secho(catalog_kind.upper(), fg=KIND_COLORS[catalog_kind], bold=True)
            db_catalog_status(catalog_kind, bucket, cluster, compare)
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
        elif compare:
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
            click.secho(catalog_kind.upper(), fg=KIND_COLORS[catalog_kind], bold=True)
            commit_hash_db = db_catalog_status(catalog_kind, bucket, cluster, compare)
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])

            sections = catalog_status(ctx, catalog_kind, include_dirty=include_dirty)

            for section in sections:
                name, parts = section
                click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
                if name:
                    click.echo(name + ":")
                    indent = "\t"
                else:
                    indent = ""

                for part in parts:
                    level, msg = part
                    if level in LEVEL_COLORS:
                        click.secho(indent + msg, fg=LEVEL_COLORS[level])
                    else:
                        click.echo(indent + msg)
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
            if commit_hash_db:
                show_diff_between_commits(commit_hash_db, ctx, catalog_kind)
            else:
                click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
                click.secho(
                    "DB catalog missing! To compare local and db catalogs, please publish your catalog!", fg="yellow"
                )
                click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
        else:
            sections = catalog_status(ctx, catalog_kind, include_dirty=include_dirty)

            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
            click.secho(catalog_kind.upper(), fg=KIND_COLORS[catalog_kind], bold=True)

            for section in sections:
                name, parts = section
                click.secho(DASHES, fg=KIND_COLORS[catalog_kind])
                if name:
                    click.echo(name + ":")
                    indent = "\t"
                else:
                    indent = ""

                for part in parts:
                    level, msg = part
                    if level in LEVEL_COLORS:
                        click.secho(indent + msg, fg=LEVEL_COLORS[level])
                    else:
                        click.echo(indent + msg)
            click.secho(DASHES, fg=KIND_COLORS[catalog_kind])


def db_catalog_status(kind, bucket, cluster, compare):
    if compare:
        query_get_metadata = f"""
                SELECT a.*, subquery.distinct_identifier_count
                FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{kind}_metadata AS a
                JOIN (
                    SELECT b.catalog_identifier, COUNT(b.catalog_identifier) AS distinct_identifier_count
                    FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{kind}_catalog AS b
                    GROUP BY b.catalog_identifier
                ) AS subquery
                ON a.version.identifier = subquery.catalog_identifier
                ORDER BY STR_TO_MILLIS(a.version.timestamp) DESC LIMIT 1;
            """
    else:
        # Query to get the metadata based on the kind of catalog
        query_get_metadata = f"""
            SELECT a.*, subquery.distinct_identifier_count
            FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{kind}_metadata AS a
            JOIN (
                SELECT b.catalog_identifier, COUNT(b.catalog_identifier) AS distinct_identifier_count
                FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{kind}_catalog AS b
                GROUP BY b.catalog_identifier
            ) AS subquery
            ON a.version.identifier = subquery.catalog_identifier;
        """

    # Execute query after filtering by catalog_identifier if provided
    res, err = execute_query(cluster, query_get_metadata)
    if err is not None:
        logger.error(err)
        return []

    try:
        resp = res.execute()

        # If result set is empty
        if len(resp) == 0:
            click.secho(
                f"No {kind} catalog found in the specified bucket...please run agentc publish to push catalogs to the DB.",
                fg="red",
            )
            logger.error("No catalogs published...")
            return []

        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho("db catalog info:")
        for row in resp:
            click.secho(
                f"""\tcatalog id: {row["version"]["identifier"]}
     \t\tpath            : {bucket}.{DEFAULT_CATALOG_SCOPE}.{kind}
     \t\tschema version  : {row['schema_version']}
     \t\tkind of catalog : {kind}
     \t\trepo version    : \n\t\t\ttime of publish: {row['version']['timestamp']}\n\t\t\tcatalog identifier: {row['version']['identifier']}
     \t\tembedding model : {row['embedding_model']}
     \t\tsource dirs     : {row['source_dirs']}
     \t\tnumber of items : {row['distinct_identifier_count']}
        """
            )
            if compare:
                return row["version"]["identifier"]
        return None
    except KeyspaceNotFoundException:
        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho(
            f"ERROR: db catalog of kind {kind} does not exist yet: please use the publish command by specifying the kind.",
            fg="red",
        )
    except ScopeNotFoundException:
        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho(
            f"ERROR: db catalog of kind {kind} does not exist yet: please use the publish command by specifying the kind.",
            fg="red",
        )


def catalog_status(ctx, kind, include_dirty=True):
    # TODO: One day implement status checks also against a CatalogDB
    # backend -- such as by validating DDL and schema versions,
    # looking for outdated items versus the local catalog, etc?

    # TODO: Validate schema versions -- if they're ahead, far behind, etc?

    catalog_path = pathlib.Path(ctx.catalog) / (kind + "-catalog.json")

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

    with catalog_path.open("r") as fp:
        catalog_desc = CatalogDescriptor.model_validate_json(fp.read())

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
                    [
                        (None, "repo is clean"),
                        (
                            None,
                            f"repo version:\n\t\ttime of publish: {version.timestamp}\n\t\tcatalog identifier: {version.identifier}",
                        ),
                    ],
                )
            )

        uninitialized_items = []

        if repo.is_dirty():
            section_parts = []

            version = VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

            # Scan the same source_dirs that were used in the last "agentc index".
            source_dirs = catalog_desc.source_dirs

            # Start a CatalogMem on-the-fly that incorporates the dirty
            # source file items which we'll use instead of the local catalog file.
            errs, catalog, uninitialized_items = index_catalog_start(
                EmbeddingModel(embedding_model_name=catalog_desc.embedding_model),
                MetaVersion(schema_version=catalog_desc.schema_version, library_version=catalog_desc.library_version),
                version,
                get_path_version,
                kind,
                catalog_path,
                source_dirs,
                scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                printer=lambda *args, **kwargs: None,
                max_errs=0,
                print_progress=False,
            )
            catalog_desc = catalog.catalog_descriptor

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
                (None, f"schema version  : {catalog_desc.schema_version}"),
                (None, f"kind of catalog : {catalog_desc.kind}"),
                (None, f"repo version    : {catalog_desc.version.identifier}"),
                (None, f"embedding model : {catalog_desc.embedding_model}"),
                (None, f"source dirs     : {catalog_desc.source_dirs}"),
                (None, f"number of items : {len(catalog_desc.items or [])}"),
            ],
        )
    )

    return sections


def show_diff_between_commits(commit_hash_2, ctx, kind):
    catalog_path = pathlib.Path(ctx.catalog) / (kind + "-catalog.json")
    with catalog_path.open("r") as fp:
        catalog_desc = CatalogDescriptor.model_validate_json(fp.read())
    commit_hash_1 = catalog_desc.version.identifier

    # Automatically determine the repository path from the current working directory
    repo = git.Repo(os.getcwd(), search_parent_directories=True)

    # Get the two commits by their hashes
    commit1 = repo.commit(commit_hash_1)
    commit2 = repo.commit(commit_hash_2)

    click.secho(DASHES, fg=KIND_COLORS[kind])
    # Get the diff between the two commits
    diff = commit1.diff(commit2)
    if len(diff) > 0:
        click.echo("Git diff from last catalog publish...")
        # Iterate through the diff to show changes
        for change in diff:
            if change.a_path != change.b_path:
                click.secho(f"File renamed or changed: {change.a_path} -> {change.b_path}", fg="yellow")

            if change.change_type == "A":
                click.secho(f"{change.a_path} was added.", fg="green")
            elif change.change_type == "D":
                click.secho(f"{change.a_path} was deleted.", fg="red")
            elif change.change_type == "M":
                click.secho(f"{change.a_path} was modified.", fg="yellow")
    else:
        click.secho(f"No changes to {kind} catalog from last commit..")
    click.secho(DASHES, fg=KIND_COLORS[kind])


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("status", __name__)

    @blueprint.route("/status")
    def route_status():
        kind = flask.request.args.get("kind", default="tool", type=str)
        include_dirty = flask.request.args.get("include_dirty", default="true", type=str).lower() == "true"

        return flask.jsonify(catalog_status(flask.current_app.config["ctx"], kind, include_dirty))
