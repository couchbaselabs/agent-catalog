from datetime import timedelta

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import CouchbaseException
from couchbase.options import ClusterOptions

from ..models.publish.model import CouchbaseConnect, Keyspace

import uuid


def get_connection(ctx, conn: CouchbaseConnect):
    cluster_url = conn.connection_url
    username = conn.username
    password = conn.password

    # Connect to Couchbase
    if cluster_url == "couchbase://127.0.0.1" or cluster_url == "couchbase://localhost":
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
        cluster.wait_until_ready(timedelta(seconds=15))
    except CouchbaseException as e:
        return f"Error connecting to couchbase : {e}"

    return cluster


def get_buckets(ctx, cluster):
    if cluster:
        buckets = cluster.buckets().get_all_buckets()
        list_buckets = []

        # Get bucket names
        for bucket_item in buckets:
            bucket_name = bucket_item.name
            list_buckets.append(bucket_name)
        return list_buckets


# TODO: define data's schema
def cmd_publish(ctx, cluster, data, keyspace: Keyspace):
    # TODO: Implement publish of the local catalog to a database.

    bucket = keyspace.bucket
    scope = keyspace.scope
    collection = keyspace.collection

    # Get bucket ref
    cb = cluster.bucket(bucket)

    # Get the bucket manager
    bucket_manager = cb.collections()

    # Create a new scope if does not exist
    try:
        scopes = bucket_manager.get_all_scopes()
        scope_exists = any(s.name == scope for s in scopes)
        if not scope_exists:
            bucket_manager.create_scope(scope)
            print(f"Scope '{scope}' created successfully.")
    except Exception as e:
        print(f"Error creating scope '{scope}\n': {e}")

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
        print(f"Error creating collection '{collection}': {e}")

    # Get collection ref
    cb_coll = cb.scope(scope).collection(collection)

    # TODO: iterate over input and upsert each tool
    # TODO: Pre-checks to allow/deny publishing to couchbase collection (git sha? doc sha?)

    print("\nUpserting data: ")
    try:
        key = uuid.uuid4().hex  # TODO: decide key to upsert each doc
        result = cb_coll.upsert(key, data)
        print(result.key, " added to keyspace")
    except Exception as e:
        print("could not insert: ", e)
        return e

    print("Successfully inserted catalog!")
