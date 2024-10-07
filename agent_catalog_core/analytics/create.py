import couchbase.cluster
import logging
import pathlib

from ..defaults import DEFAULT_AUDIT_COLLECTION
from ..defaults import DEFAULT_AUDIT_SCOPE

logger = logging.getLogger(__name__)


def create_analytics_views(cluster: couchbase.cluster.Cluster, bucket: str) -> None:
    ddls_folder = pathlib.Path(__file__).parent / "ddls"
    for ddl_file in ddls_folder.iterdir():
        with open(ddl_file, "r") as fp:
            raw_ddl_string = fp.read()
            ddl_string = (
                raw_ddl_string.replace("[BUCKET_NAME]", bucket)
                .replace("[SCOPE_NAME]", DEFAULT_AUDIT_SCOPE)
                .replace("[LOG_COLLECTION_NAME]", DEFAULT_AUDIT_COLLECTION)
            )
            print(f"Issuing the following statement: {ddl_string}")

            # TODO (GLENN): There should be a warning here (instead of an error) if Analytics is not enabled.
            ddl_result = cluster.analytics_query(ddl_string)
            for _ in ddl_result.rows():
                pass
