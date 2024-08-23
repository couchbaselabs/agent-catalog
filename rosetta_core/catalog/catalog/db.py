import click
import logging
import pickle
import typing

from ..annotation import AnnotationPredicate
from ..catalog.descriptor import CatalogDescriptor
from .catalog_base import CatalogBase
from .catalog_base import SearchResult
from rosetta_cmd.models import CouchbaseConnect

logger = logging.getLogger(__name__)


class CatalogDB(CatalogBase):
    """Represents a catalog stored in a database."""

    # TODO: This probably has fields of conn info, etc.
    catalog_descriptor: CatalogDescriptor = None

    @classmethod
    def create_vector_index(
        cls, bucket: str = "", kind: str = "tool", conn: CouchbaseConnect = ""
    ) -> tuple[str | None, Exception | None]:
        import json
        import requests

        index_to_create = f"{bucket}.rosetta-catalog.rosetta-{kind}-index"
        try:
            with open("created_indexes.p", "rb") as file:
                created_indexes_set = pickle.load(file)
        except pickle.UnpicklingError:
            print("Error unpickling the file. The file may be corrupted or not a valid pickle file.")

        if index_to_create not in created_indexes_set:
            create_vector_index_url = (
                f"http://localhost:8094/api/bucket/{bucket}/scope/rosetta-catalog/index/rosetta-{kind}-index"
            )
            headers = {
                "Content-Type": "application/json",
            }
            auth = (conn.username, conn.password)

            payload = json.dumps(
                {
                    "type": "fulltext-index",
                    "name": f"{bucket}.rosetta-catalog.rosetta-{kind}-vec",
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
                                f"rosetta-catalog.{kind}_catalog": {
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
                    # Add created index name to global set
                    created_indexes_set.add(index_to_create)
                    logger.info("add to created indexes ", created_indexes_set)
                    try:
                        with open("created_indexes.p", "wb") as file:
                            pickle.dump(created_indexes_set, file)
                    except pickle.PicklingError:
                        print("Error pickling the data. The data may not be serializable.")

                    return index_to_create, None
                elif json.loads(response.text)["status"] == "fail":
                    raise Exception(json.loads(response.text)["error"])
            except Exception as e:
                return None, e
        else:
            return index_to_create, None

    def find(
        self,
        query: str,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
        bucket: str = "",
        kind: str = "tool",
        conn: CouchbaseConnect = "",
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # TODO: If annotations have been specified, prune all tools that do not possess these annotations.

        # Create a vector index for the kind, if it does not exist
        index, err = CatalogDB.create_vector_index(bucket, kind, conn)
        if err is not None:
            click.secho(f"Error creating index: {err}", fg="red")
        else:
            logger.info(f"Index to use: {index}")

        # TODO: Perform semantic search

        # TODO: Order results

        # TODO: Apply our limit clause.
        # if limit > 0:
        #     results = results[:limit]
        # return results
