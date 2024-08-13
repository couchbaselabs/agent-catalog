from datetime import timedelta
import json

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import CouchbaseException
from couchbase.options import ClusterOptions
from ...cmd.models.publish.model import CouchbaseConnect
from pathlib import Path


def get_connection(conn: CouchbaseConnect):
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
        cluster = Cluster(cluster_url, options)
        cluster.wait_until_ready(timedelta(seconds=10))
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
            bucket_manager.create_scope(scope)
            print(f"Scope '{scope}' created successfully.")
    except Exception as e:
        return (f"Error creating scope '{scope}\n'", e)

    # Create a new collection within the scope if collection does not exist
    try:
        if scope_exists:
            collections = [c.name for s in scopes if s.name == scope for c in s.collections]
            collection_exists = collection in collections
            if not collection_exists:
                bucket_manager.create_collection(scope, collection)
                print(f"Collection '{collection}' in scope '{scope}' created successfully.")
        else:
            bucket_manager.create_collection(scope, collection)
            print(f"Collection '{collection}' in scope '{scope}' created successfully.")

    except Exception as e:
        return (f"Error creating collection '{collection}'\n", e)

    return ("Successfully created scope and collection", None)


class CustomPublishEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return super().default(o)
