import contextlib
import json
import logging
import os
import requests
import tqdm

from .models import CouchbaseConnect
from .query import execute_query
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTP_FTS_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTPS_FTS_PORT_NUMBER

logger = logging.getLogger(__name__)


def is_index_present(
    bucket: str = "", index_to_create: str = "", conn: CouchbaseConnect = None, fts_nodes_hostname: list[str] = None
) -> tuple[bool | dict | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""
    if fts_nodes_hostname is None:
        fts_nodes_hostname = []

    auth = (conn.username, conn.password)

    # Make a request to FTS until a live node is reached. If all nodes are down, try the host.
    for fts_node_hostname in fts_nodes_hostname:
        find_index_https_url = f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
        find_index_http_url = f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
        try:
            # REST call to get list of indexes, decide HTTP or HTTPS based on certificate path
            if conn.certificate is not None:
                response = requests.request("GET", find_index_https_url, auth=auth, verify=conn.certificate)
            else:
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
            else:
                raise RuntimeError("Couldn't check for the existing vector indexes!")
        except Exception:
            continue

    # if there is exception in all nodes then no nodes are alive
    return False, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")


def get_fts_nodes_hostname(conn: CouchbaseConnect = None) -> tuple[list[str] | None, Exception | None]:
    """Find the hostname of nodes with fts support for index partition creation in create_vector_index()"""

    node_info_url_http = f"http://{conn.host}:{DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER}/pools/default"
    node_info_url_https = f"https://{conn.host}:{DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER}/pools/default"
    auth = (conn.username, conn.password)

    # Make request to FTS
    try:
        # REST call to get node info
        if conn.certificate is not None:
            response = requests.request("GET", node_info_url_https, auth=auth, verify=conn.certificate)
        else:
            response = requests.request("GET", node_info_url_http, auth=auth)

        json_response = json.loads(response.text)
        # If api call was successful
        if json_response["name"] == "default":
            fts_nodes = []
            for node in json_response["nodes"]:
                if "fts" in node["services"]:
                    last_idx = node["configuredHostname"].rfind(":")
                    if last_idx == -1:
                        fts_nodes.append(node["configuredHostname"])
                    else:
                        fts_nodes.append(node["configuredHostname"][:last_idx])
            return fts_nodes, None
        else:
            return None, RuntimeError("Couldn't check for the existing fts nodes!")

    except Exception as e:
        return None, e


def create_vector_index(
    bucket: str = "",
    kind: str = "tool",
    conn: CouchbaseConnect = None,
    dim: int = None,
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""

    non_qualified_index_name = f"v1_agent_catalog_{kind}_index"
    qualified_index_name = f"{bucket}.{DEFAULT_CATALOG_SCOPE}.{non_qualified_index_name}"

    # decide on plan params
    (fts_nodes_hostname, err) = get_fts_nodes_hostname(conn)
    num_fts_nodes = len(fts_nodes_hostname)

    if num_fts_nodes == 0:
        raise ValueError(
            "No node with 'search' service found, cannot create vector index! Please ensure 'search' service is included in at least one node."
        )

    # To be on safer side make request to connection string host
    fts_nodes_hostname.append(conn.host)

    max_partition_env = os.getenv("AGENT_CATALOG_MAX_SOURCE_PARTITION")
    try:
        max_partition = int(max_partition_env) if max_partition_env is not None else 1024
    except Exception as e:
        raise ValueError(
            f"Cannot convert given value of max source partition to integer: {e}\nUpdate the environment variable 'AGENT_CATALOG_MAX_SOURCE_PARTITION' to an integer value"
        ) from e

    index_partition_env = os.getenv("AGENT_CATALOG_INDEX_PARTITION")
    try:
        index_partition = int(index_partition_env) if index_partition_env is not None else 2 * num_fts_nodes
    except Exception as e:
        raise ValueError(
            f"Cannot convert given value of index partition to integer: {e}\nUpdate the environment variable 'AGENT_CATALOG_INDEX_PARTITION' to an integer value"
        ) from e

    (index_present, err) = is_index_present(bucket, qualified_index_name, conn, fts_nodes_hostname)
    if err is not None:
        return None, err
    elif isinstance(index_present, bool) and not index_present:
        # Create the index for the first time
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
                "planParams": {"maxPartitionsPerPIndex": max_partition, "indexPartitions": index_partition},
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

        # Make a request to FTS until a live node is reached. If all nodes are down, try the host.
        for fts_node_hostname in fts_nodes_hostname:
            create_vector_index_https_url = f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
            create_vector_index_http_url = f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
            try:
                # REST call to create the index
                if conn.certificate is not None:
                    response = requests.request(
                        "PUT",
                        create_vector_index_https_url,
                        headers=headers,
                        auth=auth,
                        data=payload,
                        verify=conn.certificate,
                    )
                else:
                    response = requests.request(
                        "PUT", create_vector_index_http_url, headers=headers, auth=auth, data=payload
                    )

                if json.loads(response.text)["status"] == "ok":
                    logger.info("Created vector index!!")
                    return qualified_index_name, None
                elif json.loads(response.text)["status"] == "fail":
                    raise Exception(json.loads(response.text)["error"])
            except Exception:
                continue

        # if there is exception in all nodes then no nodes are alive
        return None, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")

    elif isinstance(index_present, dict):
        # Check if no. of fts nodes has changes since last update
        cluster_fts_partitions = index_present["planParams"]["indexPartitions"]
        if cluster_fts_partitions != index_partition:
            index_present["planParams"]["indexPartitions"] = index_partition

        # Check if the mapping already exists
        existing_fields = index_present["params"]["mapping"]["types"][f"{DEFAULT_CATALOG_SCOPE}.{kind}_catalog"][
            "properties"
        ]["embedding"]["fields"]
        existing_dims = [el["dims"] for el in existing_fields]

        if dim not in existing_dims:
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

        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(index_present)

        # Make a request to FTS until a live node is reached. If all nodes are down, try the host.
        for fts_node_hostname in fts_nodes_hostname:
            update_vector_index_https_url = f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
            update_vector_index_http_url = f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/{bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index/{non_qualified_index_name}"
            try:
                # REST call to update the index
                if conn.certificate is not None:
                    response = requests.request(
                        "PUT",
                        update_vector_index_https_url,
                        headers=headers,
                        auth=auth,
                        data=payload,
                        verify=conn.certificate,
                    )
                else:
                    response = requests.request(
                        "PUT", update_vector_index_http_url, headers=headers, auth=auth, data=payload
                    )

                if json.loads(response.text)["status"] == "ok":
                    logger.info("Updated vector index!!")
                    return "Success", None
                elif json.loads(response.text)["status"] == "fail":
                    raise Exception(json.loads(response.text)["error"])

                if json.loads(response.text)["status"] == "ok":
                    logger.info("Updated vector index!!")
                    return "Success", None
                elif json.loads(response.text)["status"] == "fail":
                    raise Exception(json.loads(response.text)["error"])

            except Exception:
                continue

        # if there is exception in all nodes then no nodes are alive
        return None, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")

    else:
        return qualified_index_name, None


def create_gsi_indexes(bucket, cluster, kind, print_progress):
    """Creates required indexes at publish"""
    progress_bar = tqdm.tqdm(range(5))
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

    # Primary index on kind_metadata
    primary_idx_metadata_name = f"v1_agent_catalog_primary_{kind}_metadata"
    primary_idx = f"""
        CREATE PRIMARY INDEX IF NOT EXISTS `{primary_idx_metadata_name}`
        ON `{bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}_metadata` USING GSI;
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
