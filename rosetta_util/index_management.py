import json
import requests

from rosetta_cmd.models import CouchbaseConnect
from rosetta_core.defaults import DEFAULT_CB_SCOPE_NAME
from rosetta_util.query import execute_query


def is_index_present(
    bucket: str = "", index_to_create: str = "", conn: CouchbaseConnect = ""
) -> tuple[bool | None, Exception | None]:
    """Checks for existence of index_to_create in the given keyspace"""

    find_index_url = f"http://localhost:8094/api/bucket/{bucket}/scope/{DEFAULT_CB_SCOPE_NAME}/index"
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
    bucket: str = "", kind: str = "tool", conn: CouchbaseConnect = ""
) -> tuple[str | None, Exception | None]:
    """Creates required vector index at publish"""

    index_to_create = f"{bucket}.{DEFAULT_CB_SCOPE_NAME}.rosetta-{kind}-index"
    index_present, err = is_index_present(bucket, index_to_create, conn)

    if err is None and not index_present:
        create_vector_index_url = (
            f"http://localhost:8094/api/bucket/{bucket}/scope/{DEFAULT_CB_SCOPE_NAME}/index/rosetta-{kind}-index"
        )
        headers = {
            "Content-Type": "application/json",
        }
        auth = (conn.username, conn.password)

        payload = json.dumps(
            {
                "type": "fulltext-index",
                "name": f"{bucket}.{DEFAULT_CB_SCOPE_NAME}.rosetta-{kind}-vec",
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
                            f"{DEFAULT_CB_SCOPE_NAME}.{kind}_catalog": {
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


def create_gsi_indexes(bucket, cluster, kind):
    """Creates required indexes at publish"""

    success = True
    all_errs = ""

    # Primary index on kind_catalog
    primary_idx = f"CREATE PRIMARY INDEX IF NOT EXISTS `rosetta_primary_{kind}cat` ON `{bucket}`.`rosetta-catalog`.`{kind}_catalog` USING GSI;"
    res, err = execute_query(cluster, primary_idx)
    if err is not None:
        all_errs += err
        success = False

    # Secondary index on catalog_identifier
    cat_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier` ON `{bucket}.`rosetta-catalog`.`{kind}_catalog`(`catalog_identifier`);"
    res, err = execute_query(cluster, cat_idx)
    if err is not None:
        all_errs += err
        success = False

    # TODO: discuss and remove if filter by annotations is not going to happen in the query
    # Secondary index on catalog_identifier + annotations
    # cat_ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_catalog_identifier_annotations` ON `{bucket}.`rosetta-catalog`.`{kind}_catalog`(`catalog_identifier`,`annotations`);"
    # res, err = execute_query(cluster, cat_ann_idx)
    # if err is not None:
    #     all_errs += err
    #     success = False

    # TODO: discuss and remove if filter by annotations is not going to happen in the query
    # Secondary index on annotations
    # ann_idx = f"CREATE INDEX IF NOT EXISTS `rosetta_{kind}cat_annotations` ON `{bucket}.`rosetta-catalog`.`{kind}_catalog`(`annotations`);"
    # res, err = execute_query(cluster, ann_idx)
    # if err is not None:
    #     all_errs += err
    #     success = False

    return success, all_errs
