import json
import requests

from rosetta_cmd.models import CouchbaseConnect
from rosetta_core.defaults import DEFAULT_CB_SCOPE_NAME


def is_index_present(
    bucket: str = "", index_to_create: str = "", conn: CouchbaseConnect = ""
) -> tuple[bool | None, Exception | None]:
    find_index_url = f"http://localhost:8094/api/bucket/{bucket}/scope/{DEFAULT_CB_SCOPE_NAME}/index"
    auth = (conn.username, conn.password)

    try:
        response = requests.request("GET", find_index_url, auth=auth)
        print(response.text)
        if json.loads(response.text)["status"] == "ok":
            created_indexes = [el for el in json.loads(response.text)["indexDefs"]["indexDefs"]]
            print(created_indexes)
            if index_to_create not in created_indexes:
                print("does not exist")
                return False, None
            return True, None
    except Exception as e:
        return None, e


def create_vector_index(
    bucket: str = "", kind: str = "tool", conn: CouchbaseConnect = ""
) -> tuple[str | None, Exception | None]:
    index_to_create = f"{bucket}.{DEFAULT_CB_SCOPE_NAME}.rosetta-{kind}-index"
    index_present, err = is_index_present(bucket, index_to_create, conn)

    if err is None and not index_present:
        print("in")
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
                                        "fields": [{"index": True, "name": "embedding", "type": "text"}],
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
            response = requests.request("PUT", create_vector_index_url, headers=headers, auth=auth, data=payload)

            if json.loads(response.text)["status"] == "ok":
                return index_to_create, None
            elif json.loads(response.text)["status"] == "fail":
                raise Exception(json.loads(response.text)["error"])
        except Exception as e:
            return None, e
    else:
        return index_to_create, None
