import click
import couchbase.cluster
import dataclasses
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
from .util import logging_command
from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog_start
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.util.query import execute_query
from agentc_core.version import VersionDescriptor
from couchbase.exceptions import KeyspaceNotFoundException
from couchbase.exceptions import ScopeNotFoundException

logger = logging.getLogger(__name__)


@logging_command(logger)
def cmd_status(
    cfg: Config = None,
    *,
    kind: list[typing.Literal["tools", "prompts"]],
    include_dirty: bool = True,
    with_db: bool = True,
    with_local: bool = True,
):
    if cfg is None:
        cfg = Config()

    # TODO (GLENN): Clean this up later (right now there are mixed references to "tool" and "tools").
    kind = [k.removesuffix("s") for k in kind]

    cluster = cfg.Cluster() if with_db else None
    for k in kind:
        click.secho(DASHES, fg=KIND_COLORS[k])
        click.secho(k.upper(), fg=KIND_COLORS[k], bold=True)

        # Display items from our DB catalog only.
        if with_db and not with_local:
            get_db_status(k, cfg.bucket, cluster, False)
            click.secho(DASHES, fg=KIND_COLORS[k])

        # Display items from both our DB and local FS catalog (and compare the two).
        elif with_db and with_local:
            # Grab our commit ID.
            commit_hash_db = get_db_status(k, cfg.bucket, cluster, True)
            click.secho(DASHES, fg=KIND_COLORS[k])

            # Display our status.
            sections: list[Section] = get_local_status(cfg, k, include_dirty=include_dirty)
            for section in sections:
                section.display()
            click.secho(DASHES, fg=KIND_COLORS[k])
            if commit_hash_db is not None:
                show_diff_between_commits(commit_hash_db, cfg, k)
            else:
                click.secho(DASHES, fg=KIND_COLORS[k])
                click.secho(
                    "DB catalog missing! To compare local FS and DB catalogs, please publish your catalog!", fg="yellow"
                )
            click.secho(DASHES, fg=KIND_COLORS[k])

        # Display items from our local FS catalog only.
        elif with_local and not with_db:
            sections: list[Section] = get_local_status(cfg, k, include_dirty=include_dirty)
            for section in sections:
                section.display()
            click.secho(DASHES, fg=KIND_COLORS[k])

        else:
            raise ValueError("Either local FS or DB catalog must be specified!")


@dataclasses.dataclass
class Section:
    @dataclasses.dataclass
    class Part:
        msg: str
        level: str | None = None

    parts: list[Part]
    kind: typing.Literal["prompt", "tool"]
    name: str | None = None

    def display(self):
        click.secho(DASHES, fg=KIND_COLORS[self.kind])
        if self.name is not None:
            click.echo(self.name + ":")
            indent = "\t"
        else:
            indent = ""

        for part in self.parts:
            if part.level is not None and part.level in LEVEL_COLORS:
                click.secho(indent + part.msg, fg=LEVEL_COLORS[part.level])
            else:
                click.echo(indent + part.msg)


def get_db_status(
    kind: typing.Literal["tool", "prompt"], bucket: str, cluster: couchbase.cluster.Cluster, compare: bool
) -> str | None:
    collection = DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
    if compare:
        query_get_metadata = f"""
                SELECT a.*, subquery.distinct_identifier_count
                FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{DEFAULT_CATALOG_METADATA_COLLECTION} AS a
                JOIN (
                    SELECT b.catalog_identifier, COUNT(b.catalog_identifier) AS distinct_identifier_count
                    FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{collection} AS b
                    GROUP BY b.catalog_identifier
                ) AS subquery
                ON a.version.identifier = subquery.catalog_identifier
                WHERE a.kind = "{kind}"
                ORDER BY a.version.timestamp DESC
                LIMIT 1;
            """
    else:
        # Query to get the metadata based on the kind of catalog
        query_get_metadata = f"""
            SELECT a.*, subquery.distinct_identifier_count
            FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{DEFAULT_CATALOG_METADATA_COLLECTION} AS a
            JOIN (
                SELECT b.catalog_identifier, COUNT(b.catalog_identifier) AS distinct_identifier_count
                FROM `{bucket}`.{DEFAULT_CATALOG_SCOPE}.{collection} AS b
                GROUP BY b.catalog_identifier
            ) AS subquery
            ON a.version.identifier = subquery.catalog_identifier
            WHERE a.kind = "{kind}";
        """

    # Execute query after filtering by catalog_identifier if provided
    res, err = execute_query(cluster, query_get_metadata)
    if err is not None:
        logger.error(err)
        return None

    try:
        resp = res.execute()

        # If result set is empty
        if len(resp) == 0:
            click.secho(
                f"No {kind} catalog found in the specified bucket...please run agentc publish to push catalogs to the DB.",
                fg="red",
            )
            logger.error("No catalogs published...")
            return None

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
    except KeyspaceNotFoundException as e:
        logger.debug(f"Swallowing exception {str(e)}.")
        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho(
            f"ERROR: db catalog of kind {kind} does not exist yet: please use the publish command by specifying the kind.",
            fg="red",
        )
    except ScopeNotFoundException as e:
        logger.debug(f"Swallowing exception {str(e)}.")
        click.secho(DASHES, fg=KIND_COLORS[kind])
        click.secho(
            f"ERROR: db catalog of kind {kind} does not exist yet: please use the publish command by specifying the kind.",
            fg="red",
        )


def get_local_status(cfg: Config, kind: typing.Literal["tool", "prompt"], include_dirty: bool = True) -> list[Section]:
    # TODO: One day implement status checks also against a CatalogDB
    # backend -- such as by validating DDL and schema versions,
    # looking for outdated items versus the local catalog, etc?

    # TODO: Validate schema versions -- if they're ahead, far behind, etc?
    if kind == "tool":
        catalog_file = cfg.CatalogPath() / DEFAULT_TOOL_CATALOG_FILE
    else:
        catalog_file = cfg.CatalogPath() / DEFAULT_PROMPT_CATALOG_FILE

    if not catalog_file.exists():
        return [
            Section(
                parts=[
                    Section.Part(
                        level="error",
                        msg=f"ERROR: local catalog of kind {kind} does not exist yet: please use the index command.",
                    )
                ],
                kind=kind,
            )
        ]

    # Grab our local FS catalog.
    with catalog_file.open("r") as fp:
        catalog_desc = CatalogDescriptor.model_validate_json(fp.read())

    # Gather our dirty files (if specified).
    sections: list[Section] = list()
    if include_dirty:
        repo, get_path_version = load_repository(pathlib.Path(os.getcwd()))
        if repo.is_dirty():
            sections.append(
                Section(
                    name="repo commit",
                    parts=[
                        Section.Part(level="warn", msg=f"repo of kind {kind} is DIRTY: please use the index command.")
                    ],
                    kind=kind,
                )
            )

        else:
            version = VersionDescriptor(
                identifier=str(repo.head.commit), timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
            )
            sections.append(
                Section(
                    name="repo commit",
                    parts=[
                        Section.Part(msg="repo is clean"),
                        Section.Part(
                            msg=f"repo version:\n\t\ttime of publish: {version.timestamp}\n"
                            f"\t\tcatalog identifier: {version.identifier}",
                        ),
                    ],
                    kind=kind,
                )
            )

            # Also consider our un-initialized items.
            uninitialized_items = []
            if repo.is_dirty():
                section_parts: list[Section.Part] = list()
                version = VersionDescriptor(is_dirty=True, timestamp=datetime.datetime.now(tz=datetime.timezone.utc))

                # Scan the same source_dirs that were used in the last "agentc index".
                source_dirs = catalog_desc.source_dirs

                # Start a CatalogMem on-the-fly that incorporates the dirty
                # source file items which we'll use instead of the local catalog file.
                errs, catalog, uninitialized_items = index_catalog_start(
                    EmbeddingModel(
                        embedding_model_name=cfg.embedding_model_name,
                        embedding_model_auth=cfg.embedding_model_auth,
                        embedding_model_url=cfg.embedding_model_url,
                    ),
                    MetaVersion(
                        schema_version=catalog_desc.schema_version, library_version=catalog_desc.library_version
                    ),
                    version,
                    get_path_version,
                    kind,
                    catalog_file,
                    source_dirs,
                    scan_directory_opts=DEFAULT_SCAN_DIRECTORY_OPTS,
                    printer=lambda *args, **kwargs: None,
                    max_errs=0,
                    print_progress=False,
                )
                catalog_desc = catalog.catalog_descriptor

                for err in errs:
                    section_parts.append(Section.Part(level="error", msg=f"ERROR: {err}"))
                else:
                    section_parts.append(Section.Part(msg="ok"))
                sections.append(Section(name="local scanning", parts=section_parts, kind=kind))

            if len(uninitialized_items) > 0:
                section_parts: list[Section.Part] = [
                    Section.Part(level=None, msg=f"dirty items count: {len(uninitialized_items)}")
                ]
                for x in uninitialized_items:
                    section_parts.append(Section.Part(msg=f"- {x.source}: {x.name}"))
                sections.append(Section(name="local dirty items", parts=section_parts, kind=kind))

        sections.append(
            Section(
                name="local catalog info",
                parts=[
                    Section.Part(msg=f"path            : {catalog_file}"),
                    Section.Part(msg=f"schema version  : {catalog_desc.schema_version}"),
                    Section.Part(msg=f"kind of catalog : {catalog_desc.kind}"),
                    Section.Part(msg=f"repo version    : {catalog_desc.version.identifier}"),
                    Section.Part(msg=f"embedding model : {catalog_desc.embedding_model}"),
                    Section.Part(msg=f"source dirs     : {catalog_desc.source_dirs}"),
                    Section.Part(msg=f"number of items : {len(catalog_desc.items or [])}"),
                ],
                kind=kind,
            )
        )
        return sections


def show_diff_between_commits(cfg: Config, commit_hash_2: str, kind: typing.Literal["tool", "prompt"]):
    if kind == "tool":
        catalog_path = cfg.CatalogPath() / DEFAULT_TOOL_CATALOG_FILE
    else:
        catalog_path = cfg.CatalogPath() / DEFAULT_PROMPT_CATALOG_FILE
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


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("status", __name__)

    @blueprint.route("/status")
    def route_status():
        kind = flask.request.args.get("kind", default="tool", type=str)
        include_dirty = flask.request.args.get("include_dirty", default="true", type=str).lower() == "true"

        return flask.jsonify(get_local_status(flask.current_app.config["ctx"], kind, include_dirty))
