import click
import couchbase.cluster
import dateparser
import importlib.util
import json
import logging
import pathlib
import typing

from ..models.context import Context
from .util import remove_directory
from agentc_core.defaults import DEFAULT_AUDIT_COLLECTION
from agentc_core.defaults import DEFAULT_AUDIT_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_LLM_ACTIVITY_NAME
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.util.query import execute_query
from json import JSONDecodeError
from typing_extensions import Literal
from tzlocal import get_localzone

logger = logging.getLogger(__name__)


def clean_local(ctx: Context | None, type_metadata: str, date: str = None):
    clean_catalog = type_metadata == "catalog" or type_metadata == "all"
    clean_activity = type_metadata == "activity" or type_metadata == "all"

    if clean_catalog:
        remove_directory(ctx.catalog)

    if clean_activity:
        if date is not None:
            req_date = dateparser.parse(date)
            local_tz = get_localzone()
            req_date = req_date.replace(tzinfo=local_tz)

            if req_date is None:
                raise ValueError(f"Invalid date provided: {date}")

            log_path = pathlib.Path(ctx.activity) / DEFAULT_LLM_ACTIVITY_NAME
            try:
                with log_path.open("r+") as fp:
                    # move file pointer to the beginning of a file
                    fp.seek(0)
                    pos = 0
                    while True:
                        line = fp.readline()
                        if not line:
                            break
                        try:
                            cur_log_timestamp = dateparser.parse(json.loads(line.strip())["timestamp"])
                            if cur_log_timestamp >= req_date:
                                break
                        except (JSONDecodeError, KeyError) as e:
                            logger.error(f"Invalid log entry: {e}")
                        pos = fp.tell()

                    # no log found before the date, might be present in old log files which are compressed
                    if pos == 0:
                        raise NotImplementedError("No log entries found before the given date in the current log!")

                    # seek to the last log before the mentioned date once again to be on safer side
                    fp.seek(pos)
                    # move file pointer to the beginning of a file and write remaining lines
                    remaining_lines = fp.readlines()
                    fp.seek(0)
                    fp.writelines(remaining_lines)
                    # truncate the file
                    fp.truncate()
            except FileNotFoundError:
                raise ValueError("No log file found! Please run auditor!") from None

        else:
            remove_directory(ctx.activity)


def clean_db(
    ctx: Context | None,
    bucket: str,
    cluster: couchbase.cluster.Cluster,
    catalog_ids: list[str],
    kind_list: list[typing.Literal["tool", "prompt"]],
    type_metadata: Literal["catalog", "activity", "all"],
    date: str = None,
) -> int:
    all_errs = []
    clean_catalog = type_metadata == "catalog" or type_metadata == "all"
    clean_activity = type_metadata == "activity" or type_metadata == "all"

    if clean_catalog:
        if len(catalog_ids) > 0:
            for kind in kind_list:
                click.secho(f"Removing catalog(s): {[catalog for catalog in catalog_ids]}", fg="yellow")

                catalog_condition = " AND ".join([f"catalog_identifier = '{catalog}'" for catalog in catalog_ids])
                meta_catalog_condition = " AND ".join([f"version.identifier = '{catalog}'" for catalog in catalog_ids])
                remove_catalogs_query = f"""
                                DELETE FROM
                                    `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_CATALOG_COLLECTION_NAME}
                                WHERE
                                    {catalog_condition};
                            """
                remove_metadata_query = f"""
                                DELETE FROM
                                    `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{kind}{DEFAULT_META_COLLECTION_NAME}
                                WHERE
                                    {meta_catalog_condition};
                            """

                res, err = execute_query(cluster, remove_catalogs_query)
                for r in res.rows():
                    logger.debug(r)
                if err is not None:
                    all_errs.append(err)

                res, err = execute_query(cluster, remove_metadata_query)
                for r in res.rows():
                    logger.debug(r)
                if err is not None:
                    all_errs.append(err)

        else:
            drop_scope_query = f"DROP SCOPE `{bucket}`.`{DEFAULT_CATALOG_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

    if clean_activity:
        if date is not None:
            req_date = dateparser.parse(date)
            local_tz = get_localzone()
            req_date = req_date.replace(tzinfo=local_tz)

            remove_catalogs_query = f"""
                            DELETE FROM
                                `{bucket}`.`{DEFAULT_AUDIT_SCOPE}`.`{DEFAULT_AUDIT_COLLECTION}`
                            WHERE
                                STR_TO_MILLIS(timestamp) < STR_TO_MILLIS('{req_date.isoformat()}');
                        """

            res, err = execute_query(cluster, remove_catalogs_query)

            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

        else:
            drop_scope_query = f"DROP SCOPE `{bucket}`.`{DEFAULT_AUDIT_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

                if len(all_errs) > 0:
                    logger.error(all_errs)

    return len(all_errs)


def cmd_clean(
    is_local: bool,
    is_db: bool,
    bucket: str,
    cluster: couchbase.cluster.Cluster,
    catalog_ids: tuple[str],
    kind: list[typing.Literal["tool", "prompt"]],
    ctx: Context = None,
    type_metadata: Literal["catalog", "activity", "all"] = "all",
    date: str = None,
):
    if is_local:
        clean_local(ctx, type_metadata, date)
        click.secho("Local catalog/metadata/logs has been deleted!", fg="green")

    if is_db:
        num_errs = clean_db(ctx, bucket, cluster, catalog_ids, kind, type_metadata, date)
        if num_errs > 0:
            raise ValueError("Failed to cleanup db catalog/metadata!")
        else:
            click.secho("Database catalog/metadata/logs has been deleted!", fg="green")


# Note: flask is an optional dependency.
if importlib.util.find_spec("flask") is not None:
    import flask

    blueprint = flask.Blueprint("clean", __name__)

    @blueprint.route("/clean", methods=["POST"])
    def route_clean():
        # TODO: Check creds as it's destructive.

        ctx = flask.current_app.config["ctx"]

        if True:  # TODO: Should check REST args on whether to clean local catalog.
            clean_local(ctx, None)

        if False:  # TODO: Should check REST args on whether to clean db.
            clean_db(ctx, "TODO", None)

        return "OK"  # TODO.
