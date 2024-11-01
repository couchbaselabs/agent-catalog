import couchbase.cluster
import logging
import pathlib

from ..defaults import DEFAULT_AUDIT_COLLECTION
from ..defaults import DEFAULT_AUDIT_SCOPE

logger = logging.getLogger(__name__)


# TODO (GLENN): There are some slight differences between query SQL++ and analytics SQL++ ...
# def create_query_udfs(cluster: couchbase.cluster.Cluster, bucket: str) -> None:
#     ddls_folder = pathlib.Path(__file__).parent / "ddls"
#     ddl_files = sorted(file for file in ddls_folder.iterdir())
#     for ddl_file in ddl_files:
#         with open(ddl_file, "r") as fp:
#             raw_ddl_string = fp.read()
#             ddl_string = (
#                 raw_ddl_string
#                 .replace('[ANALYTICS?]', '')
#                 .replace("[BUCKET_NAME]", bucket)
#                 .replace("[SCOPE_NAME]", DEFAULT_AUDIT_SCOPE)
#                 .replace("[LOG_COLLECTION_NAME]", DEFAULT_AUDIT_COLLECTION)
#             )
#             logger.debug(f"Issuing the following statement: {ddl_string}")
#             ddl_result = cluster.query(ddl_string)
#             for _ in ddl_result.rows():
#                 pass


def create_analytics_udfs(cluster: couchbase.cluster.Cluster, bucket: str) -> None:
    logger.debug("Creating analytics log scope.")
    ddl_result = cluster.analytics_query(f"""
        CREATE ANALYTICS SCOPE `{bucket}`.`{DEFAULT_AUDIT_SCOPE}`
        IF NOT EXISTS;
    """)
    for _ in ddl_result.rows():
        pass

    logger.debug("Creating analytics log collection.")
    ddl_result = cluster.analytics_query(f"""
        CREATE ANALYTICS COLLECTION
        IF NOT EXISTS
        `{bucket}`.`{DEFAULT_AUDIT_SCOPE}`.`{DEFAULT_AUDIT_COLLECTION}`
        ON `{bucket}`.`{DEFAULT_AUDIT_SCOPE}`.`{DEFAULT_AUDIT_COLLECTION}`;
    """)
    for _ in ddl_result.rows():
        pass

    # Onto to our UDF DDLs...
    ddls_folder = pathlib.Path(__file__).parent / "ddls"
    ddl_files = sorted(file for file in ddls_folder.iterdir())
    for ddl_file in ddl_files:
        with open(ddl_file, "r") as fp:
            raw_ddl_string = fp.read()
            ddl_string = (
                raw_ddl_string.replace("[ANALYTICS?]", "ANALYTICS")
                .replace("[BUCKET_NAME]", bucket)
                .replace("[SCOPE_NAME]", DEFAULT_AUDIT_SCOPE)
                .replace("[LOG_COLLECTION_NAME]", DEFAULT_AUDIT_COLLECTION)
            )
            logger.debug(f"Issuing the following statement: {ddl_string}")

            ddl_result = cluster.analytics_query(ddl_string)
            for _ in ddl_result.rows():
                pass
