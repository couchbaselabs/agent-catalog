import contextlib
import json
import logging
import requests
import tqdm
import warnings

from .models import CouchbaseConnect
from .query import execute_query
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_HTTP_FTS_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTPS_FTS_PORT_NUMBER

# TODO: Add ca certificate authentication
warnings.filterwarnings(
    action="ignore",
    message=".*Unverified HTTPS.*",
)

logger = logging.getLogger(__name__)


def is_index_present(
    bucket: str = "", index_to_create: str = "", conn: CouchbaseConnect = ""
) -> tuple[bool | dict | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""
    find_index_https_url = (
        f"https://{conn.host}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
    )
    find_index_http_url = (
        f"http://{conn.host}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
    )
    auth = (conn.username, conn.password)

    # Make HTTPS request to FTS
    try:
        # REST call to get list of indexes
        response = requests.request("GET", find_index_https_url, auth=auth, verify=False)
        json_response = json.loads(response.text)
        if json_response["status"] == "ok":
            # If no vector indexes are present
            if json_response["indexDefs"] is None:
                return False, None
            # If index_to_create not in existing vector index list
            created_indexes = [el for el in json_response["indexDefs"]["indexDefs"]]
            if index_to_create not in created_indexes:
                return False, None
            else:
                index_def = json_response["indexDefs"]["indexDefs"][index_to_create]
                return index_def, None
    except Exception:
        pass

    # Make HTTP request if in case HTTPS ports are not made public
    try:
        response = requests.request("GET", find_index_http_url, auth=auth)
        json_response = json.loads(response.text)
        if json_response["status"] == "ok":
            if json_response["indexDefs"] is None:
                return False, None
            created_indexes = [el for el in json_response["indexDefs"]["indexDefs"]]
            if index_to_create not in created_indexes:
                return False, None
            else:
                index_def = json_response["indexDefs"]["indexDefs"][index_to_create]
                return index_def, None
    except Exception as e:
        return False, e


def create_vector_index(
    bucket: str = "",
    kind: str = "tool",
    conn: CouchbaseConnect = "",
    dim: int = None,
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""

    non_qualified_index_name = f"v1_agent_catalog_{kind}_index"
    qualified_index_name = f"{bucket}.{DEFAULT_CATALOG_SCOPE}.{non_qualified_index_name}"

    (index_present, err) = is_index_present(bucket, qualified_index_name, conn)
    if err is None and isinstance(index_present, bool) and not index_present:
        # Create the index for the first time
        create_vector_index_https_url = f"https://{conn.host}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
        create_vector_index_http_url = f"http://{conn.host}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"

        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(
            {
                "type": "fulltext-index",
                "name": qualified_index_name,
                "sourceType": "gocbcore",
                "sourceName": bucket,
                "planParams": {"maxPartitionsPerPIndex": 1024, "indexPartitions": 1},
                "params": {
                    "doc_config": {
                        "docid_prefix_delim": "",
                        "docid_regexp": "",
                        "mode": "scope.collection.type_field",
                        "type_field": "type",
                    },
                    "mapping": {
                        "analysis": {},
                        "default_analyzer": "standard",
                        "default_datetime_parser": "dateTimeOptional",
                        "default_field": "_all",
                        "default_mapping": {"dynamic": True, "enabled": False},
                        "default_type": "_default",
                        "docvalues_dynamic": False,
                        "index_dynamic": True,
                        "store_dynamic": False,
                        "type_field": "_type",
                        "types": {
                            f"{DEFAULT_CATALOG_SCOPE}.{kind}_catalog": {
                                "dynamic": False,
                                "enabled": True,
                                "properties": {
                                    "embedding": {
                                        "dynamic": False,
                                        "enabled": True,
                                        "fields": [
                                            {
                                                "dims": dim,
                                                "index": True,
                                                "name": f"embedding_{dim}",
                                                "similarity": "dot_product",
                                                "type": "vector",
                                                "vector_index_optimized_for": "recall",
                                            },
                                        ],
                                    }
                                },
                            }
                        },
                    },
                    "store": {"indexType": "scorch", "segmentVersion": 16},
                },
                "sourceParams": {},
                "uuid": "",
            }
        )

        # HTTPS call
        try:
            # REST call to create the index
            response = requests.request(
                "PUT", create_vector_index_https_url, headers=headers, auth=auth, data=payload, verify=False
            )
            if json.loads(response.text)["status"] == "ok":
                logger.info("Created vector index!!")
                return qualified_index_name, None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception:
            pass

        # HTTP fallback call if HTTPS doesn't work
        try:
            response = requests.request("PUT", create_vector_index_http_url, headers=headers, auth=auth, data=payload)
            if json.loads(response.text)["status"] == "ok":
                logger.info("Created vector index!!")
                return qualified_index_name, None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e

    elif err is None and isinstance(index_present, dict):
        # Check if the mapping already exists
        existing_fields = index_present["params"]["mapping"]["types"][f"{DEFAULT_CATALOG_SCOPE}.{kind}_catalog"][
            "properties"
        ]["embedding"]["fields"]
        existing_dims = [el["dims"] for el in existing_fields]
        if dim in existing_dims:
            return None, None

        # If it doesn't, create it
        logger.debug("Updating the index...")
        # Update the index
        new_field_mapping = {
            "dims": dim,
            "index": True,
            "name": f"embedding-{dim}",
            "similarity": "dot_product",
            "type": "vector",
            "vector_index_optimized_for": "recall",
        }

        # Add field mapping with new model dim
        field_mappings = index_present["params"]["mapping"]["types"][f"{DEFAULT_CATALOG_SCOPE}.{kind}_catalog"][
            "properties"
        ]["embedding"]["fields"]
        field_mappings.append(new_field_mapping) if new_field_mapping not in field_mappings else field_mappings
        index_present["params"]["mapping"]["types"][f"{DEFAULT_CATALOG_SCOPE}.{kind}_catalog"]["properties"][
            "embedding"
        ]["fields"] = field_mappings

        update_vector_index_https_url = f"https://{conn.host}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
        update_vector_index_http_url = f"http://{conn.host}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(index_present)

        # HTTPS call
        try:
            # REST call to update the index
            response = requests.request(
                "PUT", update_vector_index_https_url, headers=headers, auth=auth, data=payload, verify=False
            )
            if json.loads(response.text)["status"] == "ok":
                logger.info("Updated vector index!!")
                return "Success", None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception:
            pass

        # HTTP fallback call if HTTPS ports are not made public
        try:
            response = requests.request("PUT", update_vector_index_http_url, headers=headers, auth=auth, data=payload)
            if json.loads(response.text)["status"] == "ok":
                logger.info("Updated vector index!!")
                return "Success", None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e

    else:
        return qualified_index_name, None


def create_gsi_indexes(bucket, cluster, kind, print_progress):
    """Creates required indexes at publish"""
    progress_bar = tqdm.tqdm(range(4))
    progress_bar_it = iter(progress_bar)

    completion_status = True
    all_errs = ""

    # Primary index on kind_catalog
    primary_idx_name = f"v1_agent_catalog_primary_{kind}"
    primary_idx = f"""
        CREATE PRIMARY INDEX IF NOT EXISTS `{primary_idx_name}`
        ON `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}_catalog` USING GSI;
"""
    if print_progress:
        next(progress_bar_it)
        progress_bar.set_description(primary_idx_name)
    res, err = execute_query(cluster, primary_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on catalog_identifier
    cat_idx_name = f"v1_agent_catalog_{kind}cat_version_identifier"
    cat_idx = f"""
        CREATE INDEX IF NOT EXISTS `{cat_idx_name}`
        ON `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}_catalog`(catalog_identifier);
    """
    if print_progress:
        next(progress_bar_it)
        progress_bar.set_description(cat_idx_name)
    res, err = execute_query(cluster, cat_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on catalog_identifier + annotations
    cat_ann_idx_name = f"v1_agent_catalog_{kind}cat_catalog_identifier_annotations"
    cat_ann_idx = f"""
        CREATE INDEX IF NOT EXISTS `{cat_ann_idx_name}`
        ON `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}_catalog`(catalog_identifier,annotations);
    """
    if print_progress:
        next(progress_bar_it)
        progress_bar.set_description(cat_ann_idx_name)
    res, err = execute_query(cluster, cat_ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on annotations
    ann_idx_name = f"v1_agent_catalog_{kind}cat_annotations"
    ann_idx = f"""
        CREATE INDEX IF NOT EXISTS `{ann_idx_name}`
        ON `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}_catalog`(`annotations`);
    """
    if print_progress:
        next(progress_bar_it)
        progress_bar.set_description(ann_idx_name)
    res, err = execute_query(cluster, ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # This is to ensure that the progress bar reaches 100% even if there are no errors.
    with contextlib.suppress(StopIteration):
        next(progress_bar_it)
    return completion_status, all_errs
