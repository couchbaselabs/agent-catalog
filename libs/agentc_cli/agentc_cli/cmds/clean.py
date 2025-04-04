import click_extra
import couchbase.cluster
import dateparser
import importlib.util
import json
import logging
import os
import pathlib
import shutil
import typing
import tzlocal

from .util import logging_command
from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_ACTIVITY_FILE
from agentc_core.defaults import DEFAULT_ACTIVITY_LOG_COLLECTION
from agentc_core.defaults import DEFAULT_ACTIVITY_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.remote.util.query import execute_query

logger = logging.getLogger(__name__)


# TODO (GLENN): We should add some granularity w.r.t. what to clean here?
def clean_local(cfg: Config, targets: list[typing.Literal["catalog", "activity"]], date: str = None):
    def remove_directory(folder: str):
        if not folder or not os.path.exists(folder):
            return
        folder_path = pathlib.Path(folder)
        if folder_path.is_file():
            os.remove(folder_path.absolute())
        elif folder_path.is_dir():
            shutil.rmtree(folder_path.absolute())

    if "catalog" in targets:
        remove_directory(cfg.CatalogPath())

    if "activity" in targets and date is None:
        remove_directory(cfg.ActivityPath())

    elif "activity" in targets and date is not None:
        req_date = dateparser.parse(date)
        if req_date is None:
            raise ValueError(f"Invalid datetime provided: {date}")

        if req_date.tzinfo is None:
            local_tz = tzlocal.get_localzone()
            req_date = req_date.replace(tzinfo=local_tz)

        if req_date is None:
            raise ValueError(f"Invalid date provided: {date}")

        # Note: this is a best-effort approach.
        log_path = cfg.ActivityPath() / DEFAULT_ACTIVITY_FILE
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
                        # Note: not using Pydantic here on purpose (we don't need / care about validation).
                        cur_log_timestamp = dateparser.parse(json.loads(line.strip())["timestamp"])
                        if cur_log_timestamp >= req_date:
                            break
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Invalid log entry encountered:{e}")
                    pos = fp.tell()

                # no log found before the date, might be present in old log files which are compressed
                if pos == 0:
                    raise NotImplementedError(
                        "No log entries found before the given date in the current log. "
                        "We currently do not support removing logs that have been compressed."
                    )

                # seek to the last log before the mentioned date once again to be on safer side
                fp.seek(pos)
                # move file pointer to the beginning of a file and write remaining lines
                remaining_lines = fp.readlines()
                fp.seek(0)
                fp.writelines(remaining_lines)
                # truncate the file
                fp.truncate()
        except FileNotFoundError as e:
            logger.warning(f"Log file not found. This is a NO-OP.\n{e}")


def clean_db(
    cfg: Config,
    catalog_ids: list[str],
    kind: list[typing.Literal["tool", "prompt"]],
    targets: list[typing.Literal["catalog", "activity"]],
    date: str = None,
) -> int:
    cluster: couchbase.cluster.Cluster = cfg.Cluster()

    # TODO (GLENN): Is there a reason we are accumulating errors here (instead of stopping on the first error)?
    all_errs = list()
    if "catalog" in targets:
        if len(catalog_ids) > 0:
            for k in kind:
                click_extra.secho(f"Removing catalog(s): {[catalog for catalog in catalog_ids]}", fg="yellow")
                meta_catalog_condition = " AND ".join([f"version.identifier = '{catalog}'" for catalog in catalog_ids])
                remove_metadata_query = f"""
                    DELETE FROM
                        `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.{DEFAULT_CATALOG_METADATA_COLLECTION}
                    WHERE
                        kind = "{k}" AND
                        {meta_catalog_condition};
                """
                res, err = execute_query(cluster, remove_metadata_query)
                for r in res.rows():
                    logger.debug(r)
                if err is not None:
                    all_errs.append(err)

                collection = DEFAULT_CATALOG_TOOL_COLLECTION if k == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
                catalog_condition = " AND ".join([f"catalog_identifier = '{catalog}'" for catalog in catalog_ids])
                remove_catalogs_query = f"""
                    DELETE FROM
                        `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection}`
                    WHERE
                        {catalog_condition};
                """
                res, err = execute_query(cluster, remove_catalogs_query)
                for r in res.rows():
                    logger.debug(r)
                if err is not None:
                    all_errs.append(err)

        else:
            drop_scope_query = f"DROP SCOPE `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

    if "activity" in targets:
        if date is not None:
            req_date = dateparser.parse(date)
            if req_date is None:
                raise ValueError(f"Invalid datetime provided: {date}")

            if req_date.tzinfo is None:
                local_tz = tzlocal.get_localzone()
                req_date = req_date.replace(tzinfo=local_tz)

            remove_catalogs_query = f"""
                DELETE FROM
                    `{cfg.bucket}`.`{DEFAULT_ACTIVITY_SCOPE}`.`{DEFAULT_ACTIVITY_LOG_COLLECTION}` l
                WHERE
                    STR_TO_MILLIS(l.timestamp) < STR_TO_MILLIS('{req_date.isoformat()}');
            """

            res, err = execute_query(cluster, remove_catalogs_query)

            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

        else:
            drop_scope_query = f"DROP SCOPE `{cfg.bucket}`.`{DEFAULT_ACTIVITY_SCOPE}` IF EXISTS;"
            res, err = execute_query(cluster, drop_scope_query)
            for r in res.rows():
                logger.debug(r)
            if err is not None:
                all_errs.append(err)

    if len(all_errs) > 0:
        logger.error(all_errs)

    return len(all_errs)


@logging_command(logger)
def cmd_clean(
    cfg: Config = None,
    *,
    is_local: bool,
    is_db: bool,
    catalog_ids: tuple[str],
    kind: list[typing.Literal["tool", "prompt"]],
    targets: list[typing.Literal["catalog", "activity"]],
    date: str = None,
):
    if cfg is None:
        cfg = Config()

    if is_local:
        clean_local(cfg, targets, date)
        click_extra.secho("Local FS catalog/metadata has been deleted!", fg="green")

    if is_db:
        num_errs = clean_db(cfg, catalog_ids, kind, targets, date)
        if num_errs > 0:
            raise ValueError("Failed to cleanup DB catalog/metadata!")
        else:
            click_extra.secho("Database catalog/metadata has been deleted!", fg="green")


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

        # if False:  # TODO: Should check REST args on whether to clean db.
        #     clean_db(ctx, "TODO", None)

        return "OK"  # TODO.
