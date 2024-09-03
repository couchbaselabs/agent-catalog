import json
import logging
import requests

from rosetta_cmd.defaults import DEFAULT_SCOPE_PREFIX
from rosetta_cmd.models import CouchbaseConnect
from rosetta_util.query import execute_query

logger = logging.getLogger(__name__)


def is_index_present(
    bucket: str = "", scope_name: str = "", index_to_create: str = "", conn: CouchbaseConnect = ""
) -> tuple[bool | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""

    find_index_url = f"http://localhost:8094/api/bucket/{bucket}/scope/{scope_name}/index"
    auth = (conn.username, conn.password)

    try:
        # REST call to get list of indexes
        response = requests.request("GET", find_index_url, auth=auth)

        if json.loads(response.text)["status"] == "ok":
            created_indexes = [el for el in json.loads(response.text)["indexDefs"]["indexDefs"]]
            if index_to_create not in created_indexes:
                return False, None
            return True, None
    except Exception as e:
        return None, e


def create_vector_index(
    bucket: str = "", kind: str = "tool", conn: CouchbaseConnect = "", embedding_model: str = ""
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""

    scope_name = DEFAULT_SCOPE_PREFIX + embedding_model
    index_to_create = f"{bucket}.{scope_name}.rosetta-{kind}-index-{embedding_model}"
    index_present, err = is_index_present(bucket, scope_name, index_to_create, conn)

    if err is None and not index_present:
        create_vector_index_url = (
            f"http://localhost:8094/api/bucket/{bucket}/scope/{scope_name}/index/rosetta-{kind}-index-{embedding_model}"
        )
        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(
            {
                "type": "fulltext-index",
                "name": f"{bucket}.{scope_name}.rosetta-{kind}-vec",
                "sourceType": "gocbcore",
                "sourceName": f"{bucket}",
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
                            f"{scope_name}.{kind}_catalog": {
                                "dynamic": False,
                                "enabled": True,
                                "properties": {
                                    "embedding": {
                                        "dynamic": False,
                                        "enabled": True,
                                        "fields": [
                                            {
                                                "index": True,
                                                "name": "embedding",
                                                "type": "vector",
                                                "similarity": "dot_product",
                                                "vector_index_optimized_for": "recall",
                                                "dims": 384,
                                            }
                                        ],
                                    }
                                },
                            }
                        },
                    },
                    "store": {"indexType": "scorch", "segmentVersion": 15},
                },
                "sourceParams": {},
            }
        )

        try:
            # REST call to create the index
            response = requests.request("PUT", create_vector_index_url, headers=headers, auth=auth, data=payload)

            if json.loads(response.text)["status"] == "ok":
                return index_to_create, None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e
    else:
        return index_to_create, None


def create_gsi_indexes(bucket, cluster, kind, embedding_model):
    """Creates required indexes at publish"""

    success = True
    all_errs = ""
    scope_name = DEFAULT_SCOPE_PREFIX + embedding_model

    # Primary index on kind_catalog
    primary_idx = f"CREATE PRIMARY INDEX IF NOT EXISTS `rosetta_primary_{kind}cat_{embedding_model}` ON `{bucket}`.`{scope_name}`.`{kind}_catalog` USING GSI;"
    res, err = execute_query(cluster, primary_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        success = False

    # Secondary index on catalog_identifier
    cat_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier_{embedding_model}` ON `{bucket}`.`{scope_name}`.`{kind}_catalog`(`catalog_identifier`);"
    res, err = execute_query(cluster, cat_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        success = False

    # Secondary index on catalog_identifier + annotations
    cat_ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier_annotations_{embedding_model}` ON `{bucket}`.`{scope_name}`.`{kind}_catalog`(`catalog_identifier`,`annotations`);"
    res, err = execute_query(cluster, cat_ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        success = False

    # Secondary index on annotations
    ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_annotations_{embedding_model}` ON `{bucket}`.`{scope_name}`.`{kind}_catalog`(`annotations`);"
    res, err = execute_query(cluster, ann_idx)
    for r in res.rows():
        logger.debug(r)
    if err is not None:
        all_errs += err
        success = False

    return success, all_errs
