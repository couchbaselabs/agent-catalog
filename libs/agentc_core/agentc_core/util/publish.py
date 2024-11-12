import logging

from .models import CouchbaseConnect
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import CouchbaseException
from couchbase.options import ClusterOptions
from datetime import timedelta

logger = logging.getLogger(__name__)


def get_connection(conn: CouchbaseConnect) -> tuple[str, None] | tuple[None, Cluster]:
    """Get cluster object by connecting to user's Couchbase cluster"""

    cluster_url = conn.connection_url
    username = conn.username
    password = conn.password
    certificate = conn.certificate

    # Connect to Couchbase
    auth = (
        PasswordAuthenticator(username, password)
        if certificate is None
        else PasswordAuthenticator(username, password, cert_path=certificate)
    )
    options = ClusterOptions(auth)
    options.apply_profile("wan_development")

    try:
        logger.debug(f"Connecting to Couchbase cluster at {cluster_url}...")
        cluster = Cluster(cluster_url, options)
        cluster.wait_until_ready(timedelta(seconds=10))
        logger.debug("Connection successfully established.")

    except CouchbaseException as e:
        return e.message, None

    return None, cluster


def get_buckets(cluster):
    """Get list of buckets from user's Couchbase cluster"""

    if cluster:
        buckets = cluster.buckets().get_all_buckets()
        list_buckets = []

        # Get bucket names
        for bucket_item in buckets:
            bucket_name = bucket_item.name
            list_buckets.append(bucket_name)
        return list_buckets


def create_scope_and_collection(bucket_manager, scope, collection):
    """Create new Couchbase scope and collection within it if they do not exist"""
    # TODO (GLENN): Refactor to just use cluster.query and CREATE SCOPE and CREATE COLLECTION statements
    #               (you can use IF NOT EXISTS instead of checking if the scope / collection exists)

    # Create a new scope if it does not exist
    try:
        scopes = bucket_manager.get_all_scopes()
        scope_exists = any(s.name == scope for s in scopes)
        if not scope_exists:
            logger.debug(f"Scope {scope} not found. Attempting to create scope now.")
            bucket_manager.create_scope(scope)
            logger.debug(f"Scope {scope} was created successfully.")
    except CouchbaseException as e:
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
                bucket_manager.create_collection(scope, collection)
                logger.debug(f"Collection {scope}.{collection} was created successfully.")
        else:
            logger.debug(f"Collection {scope}.{collection} not found. Attempting to create collection now.")
            bucket_manager.create_collection(scope, collection)
            logger.debug(f"Collection {scope}.{collection} was created successfully.")

    except CouchbaseException as e:
        error_message = f"Encountered error while creating collection {scope}.{collection}:\n{e.message}"
        logger.error(error_message)
        return error_message, e

    return "Successfully created scope and collection", None
