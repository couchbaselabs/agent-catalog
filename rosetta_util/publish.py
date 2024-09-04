import json
import logging
import typing

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import CouchbaseException
from couchbase.options import ClusterOptions
from datetime import timedelta
from pathlib import Path

# TODO (GLENN): Should this model be pushed into this module?
from rosetta_cmd.models.publish import CouchbaseConnect

logger = logging.getLogger(__name__)


def get_connection(conn: CouchbaseConnect) -> typing.Tuple[str, Cluster]:
    cluster_url = conn.connection_url
    username = conn.username
    password = conn.password

    # Connect to Couchbase
    if cluster_url == "localhost" or cluster_url == "couchbase://localhost":
        auth = PasswordAuthenticator(username, password)
        options = ClusterOptions(auth)
        options.apply_profile("wan_development")
    else:
        # Connect to Capella
        auth = PasswordAuthenticator(username, password, cert_path="certificates/cert.pem")
        options = ClusterOptions(auth)
        options.apply_profile("wan_development")

    try:
        logger.debug(f"Connecting to Couchbase cluster at {cluster_url}...")
        cluster = Cluster(cluster_url, options)
        cluster.wait_until_ready(timedelta(seconds=10))
        logger.debug("Connection successfully established.")

    except CouchbaseException as e:
        return f"Error connecting to couchbase : {e}", None

    return None, cluster


def get_buckets(cluster):
    if cluster:
        buckets = cluster.buckets().get_all_buckets()
        list_buckets = []

        # Get bucket names
        for bucket_item in buckets:
            bucket_name = bucket_item.name
            list_buckets.append(bucket_name)
        return list_buckets


def create_scope_and_collection(bucket_manager, scope, collection):
    # Create a new scope if does not exist
    try:
        scopes = bucket_manager.get_all_scopes()
        scope_exists = any(s.name == scope for s in scopes)
        if not scope_exists:
            logger.debug(f"Scope {scope} not found. Attempting to create scope now.")
            bucket_manager.create_scope(scope)
            logger.debug(f"Scope {scope} was created successfully.")
    except CouchbaseException as e:
        error_message = f"Encountered error while creating scope {scope}:\n{str(e)}"
        logger.error(error_message)
        return error_message, e

    # Create a new collection within the scope if collection does not exist
    try:
        if scope_exists:
            collections = [c.name for s in scopes if s.name == scope for c in s.collections]
            collection_exists = collection in collections
            if not collection_exists:
                logger.debug(f"Collection {scope}.{collection} not found. Attempting to create collection now.")
                bucket_manager.create_collection(scope, collection)
                logger.debug(f"Collection {scope}.{collection} was created successfully.")
        else:
            logger.debug(f"Collection {scope}.{collection} not found. Attempting to create collection now.")
            bucket_manager.create_collection(scope, collection)
            logger.debug(f"Collection {scope}.{collection} was created successfully.")

    except CouchbaseException as e:
        error_message = f"Encountered error while creating collection {scope}.{collection}:\n{str(e)}"
        logger.error(error_message)
        return error_message, e

    return "Successfully created scope and collection", None


class CustomPublishEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return super().default(o)
