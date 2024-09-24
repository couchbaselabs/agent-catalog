import click
import json
import logging
import requests


# TODO (GLENN): rosetta_cmd should not be a dependency for rosetta_util
from .models import CouchbaseConnect
from .query import execute_query
from rosetta_cmd.defaults import DEFAULT_SCOPE_PREFIX
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_index_present(
    bucket: str = "", index_to_create: str = "", conn: CouchbaseConnect = ""
) -> tuple[bool | dict | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""

    url = conn.connection_url
    host = urlparse(url).netloc
    port = "8094"
    find_index_url = f"http://{host}:{port}/api/bucket/{bucket}/scope/{DEFAULT_SCOPE_PREFIX}/index"
    auth = (conn.username, conn.password)

    try:
        # REST call to get list of indexes
        response = requests.request("GET", find_index_url, auth=auth)
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
    except Exception as e:
        return False, e


def create_vector_index(
    bucket: str = "", kind: str = "tool", conn: CouchbaseConnect = "", dim: int = None, catalog_schema_ver: str = None
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""

    index_to_create = f"{bucket}.{DEFAULT_SCOPE_PREFIX}.rosetta_{kind}_index_{catalog_schema_ver}"
    (index_present, err) = is_index_present(bucket, index_to_create, conn)
    url = conn.connection_url  # should be of the format couchbase://localhost or similar
    host = urlparse(url).netloc
    port = "8094"

    if err is None and isinstance(index_present, bool) and not index_present:
        click.echo("Creating vector index...")
        # Create the index for the first time
        create_vector_index_url = f"http://{host}:{port}/api/bucket/{bucket}/scope/{DEFAULT_SCOPE_PREFIX}/index/rosetta_{kind}_index_{catalog_schema_ver}"
        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(
            {
                "type": "fulltext-index",
                "name": index_to_create,
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
                            f"{DEFAULT_SCOPE_PREFIX}.{kind}_catalog": {
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

        try:
            # REST call to create the index
            response = requests.request("PUT", create_vector_index_url, headers=headers, auth=auth, data=payload)

            if json.loads(response.text)["status"] == "ok":
                logger.info("Created vector index!!")
                return index_to_create, None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e
    elif err is None and isinstance(index_present, dict):
        # Check if the mapping already exists
        existing_fields = index_present["params"]["mapping"]["types"][f"{DEFAULT_SCOPE_PREFIX}.{kind}_catalog"][
            "properties"
        ]["embedding"]["fields"]
        existing_dims = [el["dims"] for el in existing_fields]
        if dim in existing_dims:
            return None, None

        # If it doesn't, create it
        click.echo("\nUpdating the index....")
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
        field_mappings = index_present["params"]["mapping"]["types"][f"{DEFAULT_SCOPE_PREFIX}.{kind}_catalog"][
            "properties"
        ]["embedding"]["fields"]
        field_mappings.append(new_field_mapping) if new_field_mapping not in field_mappings else field_mappings
        index_present["params"]["mapping"]["types"][f"{DEFAULT_SCOPE_PREFIX}.{kind}_catalog"]["properties"][
            "embedding"
        ]["fields"] = field_mappings

        update_vector_index_url = f"http://{host}:{port}/api/bucket/{bucket}/scope/{DEFAULT_SCOPE_PREFIX}/index/rosetta_{kind}_index_{catalog_schema_ver}"
        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(index_present)

        try:
            # REST call to update the index
            response = requests.request("PUT", update_vector_index_url, headers=headers, auth=auth, data=payload)

            if json.loads(response.text)["status"] == "ok":
                logger.info("Updated vector index!!")
                return "Success", None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e
    else:
        return index_to_create, None


def create_gsi_indexes(bucket, cluster, kind, catalog_schema_version):
    """Creates required indexes at publish"""

    completion_status = True
    all_errs = ""

    # Primary index on kind_catalog
    primary_idx = f"CREATE PRIMARY INDEX IF NOT EXISTS `rosetta_primary_{kind}cat_{catalog_schema_version}` ON `{bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{kind}_catalog` USING GSI;"
    res, err = execute_query(cluster, primary_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on catalog_identifier
    cat_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier_{catalog_schema_version}` ON `{bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{kind}_catalog`(`catalog_identifier`);"
    res, err = execute_query(cluster, cat_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on catalog_identifier + annotations
    cat_ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier_annotations_{catalog_schema_version}` ON `{bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{kind}_catalog`(`catalog_identifier`,`annotations`);"
    res, err = execute_query(cluster, cat_ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    # Secondary index on annotations
    ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_annotations_{catalog_schema_version}` ON `{bucket}`.`{DEFAULT_SCOPE_PREFIX}`.`{kind}_catalog`(`annotations`);"
    res, err = execute_query(cluster, ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        completion_status = False

    return completion_status, all_errs
