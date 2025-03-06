import contextlib
import couchbase.bucket
import couchbase.cluster
import couchbase.exceptions
import couchbase.management.collections
import json
import logging
import requests
import time
import tqdm
import typing

from agentc_core.config import Config
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_PROMPT_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_CATALOG_TOOL_COLLECTION
from agentc_core.defaults import DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTP_FTS_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER
from agentc_core.defaults import DEFAULT_HTTPS_FTS_PORT_NUMBER
from agentc_core.remote.util.query import execute_query

logger = logging.getLogger(__name__)


def get_host_name(url: str):
    # exception is handled by Pydantic class for URL, so does not matter what is returned here for None
    if url is None:
        return ""

    split_url = url.split("//")
    num_elements = len(split_url)
    if num_elements == 2:
        return split_url[1]
    elif num_elements == 1:
        return split_url[0]
    else:
        return ""


def is_fts_index_present(
    cfg: Config, index_to_create: str, fts_nodes_hostname: list[str] = None
) -> tuple[bool | dict | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""
    if fts_nodes_hostname is None:
        fts_nodes_hostname = []

    auth = (cfg.username, cfg.password.get_secret_value())

    # Make a request to FTS until a live node is reached. If all nodes are down, try the host.
    for fts_node_hostname in fts_nodes_hostname:
        find_index_https_url = (
            f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/"
            f"{cfg.bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
        )
        find_index_http_url = (
            f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/"
            f"{cfg.bucket}/scope/{DEFAULT_CATALOG_SCOPE}/index"
        )
        try:
            # REST call to get list of indexes, decide HTTP or HTTPS based on certificate path
            if cfg.conn_root_certificate is not None:
                response = requests.request("GET", find_index_https_url, auth=auth, verify=cfg.conn_root_certificate)
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

        # TODO (GLENN): Catch a narrower exception here + log the fact an exception was raised.
        except Exception as e:
            logger.debug(f"Swallowing exception {str(e)}.")
            continue

    # if there is exception in all nodes then no nodes are alive
    return False, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")


def get_fts_nodes_hostname(cfg: Config) -> tuple[list[str] | None, Exception | None]:
    """Find the hostname of nodes with fts support for index partition creation in create_vector_index()"""

    host = get_host_name(cfg.conn_string)
    node_info_url_http = f"http://{host}:{DEFAULT_HTTP_CLUSTER_ADMIN_PORT_NUMBER}/pools/default"
    node_info_url_https = f"https://{host}:{DEFAULT_HTTPS_CLUSTER_ADMIN_PORT_NUMBER}/pools/default"
    auth = (cfg.username, cfg.password.get_secret_value())

    # Make request to FTS
    try:
        # REST call to get node info
        if cfg.conn_root_certificate is not None:
            response = requests.request("GET", node_info_url_https, auth=auth, verify=cfg.conn_root_certificate)
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

    # TODO (GLENN): Catch a narrower exception here + log the fact an exception was raised.
    except Exception as e:
        return None, e


def create_vector_index(
    cfg: Config,
    scope: str,
    collection: str,
    index_name: str,
    dim: int,
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""
    qualified_index_name = f"{cfg.bucket}.{scope}.{index_name}"

    # decide on plan params
    (fts_nodes_hostname, err) = get_fts_nodes_hostname(cfg)
    num_fts_nodes = len(fts_nodes_hostname)
    if cfg.index_partition is None:
        cfg.index_partition = 2 * num_fts_nodes

    if num_fts_nodes == 0:
        raise ValueError(
            "No node with 'search' service found, cannot create vector index! "
            "Please ensure 'search' service is included in at least one node."
        )

    # To be on safer side make request to connection string host
    fts_nodes_hostname.append(get_host_name(cfg.conn_string))

    (index_present, err) = is_fts_index_present(cfg, qualified_index_name, fts_nodes_hostname)
    if err is not None:
        return None, err
    elif isinstance(index_present, bool) and not index_present:
        # Create the index for the first time
        headers = {
            "Content-Type": "application/json",
        }
        auth = (cfg.username, cfg.password.get_secret_value())

        payload = json.dumps(
            {
                "type": "fulltext-index",
                "name": qualified_index_name,
                "sourceType": "gocbcore",
                "sourceName": cfg.bucket,
                "planParams": {
                    "maxPartitionsPerPIndex": cfg.max_index_partition,
                    "indexPartitions": cfg.index_partition,
                },
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
                            f"{scope}.{collection}": {
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
            create_vector_index_https_url = (
                f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/"
                f"{cfg.bucket}/scope/{scope}/index/{index_name}"
            )
            create_vector_index_http_url = (
                f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/"
                f"{cfg.bucket}/scope/{scope}/index/{index_name}"
            )
            try:
                # REST call to create the index
                if cfg.conn_root_certificate is not None:
                    response = requests.request(
                        "PUT",
                        create_vector_index_https_url,
                        headers=headers,
                        auth=auth,
                        data=payload,
                        verify=cfg.conn_root_certificate,
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

            # TODO (GLENN): Catch a narrower exception here + log the fact an exception was raised.
            except Exception as e:
                logger.debug(f"Swallowing exception {str(e)}.")
                continue

        # if there is exception in all nodes then no nodes are alive
        return None, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")

    elif isinstance(index_present, dict):
        # Check if no. of fts nodes has changes since last update
        cluster_fts_partitions = index_present["planParams"]["indexPartitions"]
        if cluster_fts_partitions != cfg.index_partition:
            index_present["planParams"]["indexPartitions"] = cfg.index_partition

        # Check if the mapping already exists
        existing_fields = index_present["params"]["mapping"]["types"][f"{scope}.{collection}"]["properties"][
            "embedding"
        ]["fields"]
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
            field_mappings = index_present["params"]["mapping"]["types"][f"{scope}.{collection}"]["properties"][
                "embedding"
            ]["fields"]
            field_mappings.append(new_field_mapping) if new_field_mapping not in field_mappings else field_mappings
            index_present["params"]["mapping"]["types"][f"{scope}.{collection}"]["properties"]["embedding"][
                "fields"
            ] = field_mappings

        headers = {
            "Content-Type": "application/json",
        }
        auth = (cfg.username, cfg.password.get_secret_value())

        payload = json.dumps(index_present)

        # Make a request to FTS until a live node is reached. If all nodes are down, try the host.
        for fts_node_hostname in fts_nodes_hostname:
            update_vector_index_https_url = (
                f"https://{fts_node_hostname}:{DEFAULT_HTTPS_FTS_PORT_NUMBER}/api/bucket/"
                f"{cfg.bucket}/scope/{scope}/index/{index_name}"
            )
            update_vector_index_http_url = (
                f"http://{fts_node_hostname}:{DEFAULT_HTTP_FTS_PORT_NUMBER}/api/bucket/"
                f"{cfg.bucket}/scope/{scope}/index/{index_name}"
            )
            try:
                # REST call to update the index
                if cfg.conn_root_certificate is not None:
                    response = requests.request(
                        "PUT",
                        update_vector_index_https_url,
                        headers=headers,
                        auth=auth,
                        data=payload,
                        verify=cfg.conn_root_certificate,
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

            # TODO (GLENN): Catch a narrower exception here + log the fact an exception was raised.
            except Exception as e:
                logger.debug(f"Swallowing exception {str(e)}.")
                continue

        # if there is exception in all nodes then no nodes are alive
        return None, RuntimeError("Couldn't make request to any of the nodes with 'search' service!")

    else:
        return qualified_index_name, None


def create_gsi_indexes(cfg: Config, kind: typing.Literal["tool", "prompt", "metadata"], print_progress):
    """Creates required indexes at publish"""
    progress_bar = tqdm.tqdm(range(3 if kind != "metadata" else 1))
    progress_bar_it = iter(progress_bar)
    completion_status = True
    all_errs = ""

    cluster = cfg.Cluster()
    if kind == "metadata":
        # Primary index on kind_metadata
        primary_idx_metadata_name = "v2_AgentCatalogMetadataPrimaryIndex"
        primary_idx = f"""
            CREATE PRIMARY INDEX IF NOT EXISTS `{primary_idx_metadata_name}`
            ON `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{DEFAULT_CATALOG_METADATA_COLLECTION}` USING GSI;
        """
        if print_progress:
            next(progress_bar_it)
            progress_bar.set_description(primary_idx_metadata_name)
        err = None
        for _ in range(cfg.ddl_retry_attempts):
            res, err = execute_query(cluster, primary_idx)
            try:
                for r in res.rows():
                    logger.debug(r)
                break
            except couchbase.exceptions.CouchbaseException as e:
                logger.debug("Could not create primary index. Retrying and swallowing exception %s.", e)
                time.sleep(cfg.ddl_retry_wait_seconds)
                err = e
        if err is not None:
            all_errs += err
            completion_status = False
        with contextlib.suppress(StopIteration):
            next(progress_bar_it)
        return completion_status, all_errs

    # Primary index on kind_catalog
    collection = DEFAULT_CATALOG_TOOL_COLLECTION if kind == "tool" else DEFAULT_CATALOG_PROMPT_COLLECTION
    primary_idx_name = f"v2_AgentCatalog{kind.capitalize()}sPrimaryIndex"
    primary_idx = f"""
        CREATE PRIMARY INDEX IF NOT EXISTS `{primary_idx_name}`
        ON `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection}` USING GSI;
    """
    if print_progress:
        next(progress_bar_it)
        progress_bar.set_description(primary_idx_name)
    err = None
    for _ in range(cfg.ddl_retry_attempts):
        res, err = execute_query(cluster, primary_idx)
        try:
            for r in res.rows():
                logger.debug(r)
            break
        except couchbase.exceptions.CouchbaseException as e:
            logger.debug("Could not create primary index. Retrying and swallowing exception %s.", e)
            time.sleep(cfg.ddl_retry_wait_seconds)
            err = e
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on catalog_identifier + annotations
    cat_ann_idx_name = f"v2_AgentCatalog{kind.capitalize()}sCatalogIdentifierAnnotationsIndex"
    cat_ann_idx = f"""
        CREATE INDEX IF NOT EXISTS `{cat_ann_idx_name}`
        ON `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection}`(catalog_identifier,annotations);
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
    ann_idx_name = f"v2_AgentCatalog{kind.capitalize()}sAnnotationsIndex"
    ann_idx = f"""
        CREATE INDEX IF NOT EXISTS `{ann_idx_name}`
        ON `{cfg.bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{collection}`(`annotations`);
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


def check_if_scope_collection_exist(
    collection_manager: couchbase.bucket.CollectionManager, scope: str, collection: str, raise_exception: bool
) -> bool:
    """Check if the given scope and collection exist in the bucket"""
    scopes = collection_manager.get_all_scopes()
    scope_exists = any(s.name == scope for s in scopes)
    if not scope_exists:
        if raise_exception:
            raise ValueError(
                f"Scope {scope} not found in the given bucket!\n"
                f"Please use 'agentc init' command first.\n"
                f"Execute 'agentc init --help' for more information."
            )
        return False

    collections = [c.name for s in scopes if s.name == scope for c in s.collections]
    collection_exists = collection in collections
    if not collection_exists:
        if raise_exception:
            raise ValueError(
                f"Collection {scope}.{collection} not found in the given bucket!\n"
                f"Please use 'agentc init' command first.\n"
                f"Execute 'agentc init --help' for more information."
            )
        return False

    return True


def create_scope_and_collection(
    collection_manager: couchbase.management.collections.CollectionManager,
    scope: str,
    collection: str,
    ddl_retry_attempts: int,
    ddl_retry_wait_seconds: float,
):
    """Create new Couchbase scope and collection within it if they do not exist"""

    # Create a new scope if it does not exist
    try:
        scopes = collection_manager.get_all_scopes()
        scope_exists = any(s.name == scope for s in scopes)
        if not scope_exists:
            logger.debug(f"Scope {scope} not found. Attempting to create scope now.")
            collection_manager.create_scope(scope_name=scope)
            logger.debug(f"Scope {scope} was created successfully.")
    except couchbase.exceptions.CouchbaseException as e:
        error_message = f"Encountered error while creating scope {scope}:\n{e.message}"
        logger.error(error_message)
        return error_message, e

    # Create a new collection within the scope if collection does not exist
    try:
        if scope_exists:
            collections = [c.name for s in scopes if s.name == scope for c in s.collections]
            collection_exists = collection in collections
            if not collection_exists:
                logger.debug(f"Collection {scope}.{collection} not found. Attempting to create collection now.")
                collection_manager.create_collection(scope_name=scope, collection_name=collection)
                logger.debug(f"Collection {scope}.{collection} was created successfully.")
        else:
            logger.debug(f"Collection {scope}.{collection} not found. Attempting to create collection now.")
            collection_manager.create_collection(scope_name=scope, collection_name=collection)
            logger.debug(f"Collection {scope}.{collection} was created successfully.")

    except couchbase.exceptions.CouchbaseException as e:
        error_message = f"Encountered error while creating collection {scope}.{collection}:\n{e.message}"
        logger.error(error_message)
        return error_message, e

    for _ in range(ddl_retry_attempts):
        if not check_if_scope_collection_exist(collection_manager, scope, collection, raise_exception=False):
            logger.debug("Scope and collection not found. Retrying...")
            time.sleep(ddl_retry_wait_seconds)
        else:
            break

    return "Successfully created scope and collection", None
