import docker
import docker.models.containers
import http
import logging
import os
import pytest
import requests
import requests.adapters
import time
import typing
import uuid

logger = logging.getLogger(__name__)

DEFAULT_COUCHBASE_CONN_STRING = "couchbase://localhost"
DEFAULT_COUCHBASE_USERNAME = "Administrator"
DEFAULT_COUCHBASE_PASSWORD = "password"


# For whatever reason, the HTTP Retry adapter isn't working for me.
def _execute_with_retry(
    func: typing.Callable, condition: typing.Callable[..., bool], retry_count: int, backoff_factor: float = 0.1
):
    for i in range(retry_count):
        try:
            result = func()
            if condition(result):
                return result
        except Exception as e:
            logger.debug(f"Function failed with error: {str(e)}")
            if i == retry_count - 1:
                raise e
        time.sleep(backoff_factor * (2**i))


def _start_couchbase(retry_count: int = 5, backoff_factor: float = 0.7) -> docker.models.containers.Container:
    # Start the Couchbase container.
    client = docker.from_env()
    ports = {f"{port}/tcp": port for port in range(8091, 8098)}
    ports |= {f"{port}/tcp": port for port in range(18091, 18098)}
    ports |= {
        "9123/tcp": 9123,
        "11207/tcp": 11207,
        "11210/tcp": 11210,
        "11280/tcp": 11280,
    }
    container: docker.models.containers.Container = client.containers.run(
        image="couchbase", name=f"agentc_{uuid.uuid4().hex}", ports=ports, detach=True, auto_remove=True, remove=True
    )

    try:
        # Initialize the cluster.
        def _init_cluster():
            return requests.post(
                "http://localhost:8091/clusterInit",
                data={
                    "username": DEFAULT_COUCHBASE_USERNAME,
                    "password": DEFAULT_COUCHBASE_PASSWORD,
                    "services": "kv,index,n1ql,fts,cbas",
                    "clusterName": "agentc",
                    "indexerStorageMode": "plasma",
                    "port": "SAME",
                },
            )

        _execute_with_retry(
            func=_init_cluster,
            condition=lambda r: r.status_code == http.HTTPStatus.OK,
            retry_count=retry_count,
            backoff_factor=backoff_factor,
        )

        # Install the travel-sample bucket.
        def _install_bucket():
            return requests.post(
                "http://localhost:8091/sampleBuckets/install",
                auth=(DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD),
                data='["travel-sample"]',
            )

        _execute_with_retry(
            func=_install_bucket,
            condition=lambda r: r.status_code == http.HTTPStatus.ACCEPTED,
            retry_count=retry_count,
            backoff_factor=backoff_factor,
        )

        # Wait for the travel-sample bucket to be ready.
        def _is_bucket_ready():
            return requests.get(
                "http://localhost:8091/pools/default/buckets/travel-sample",
                auth=(DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD),
            )

        _execute_with_retry(
            func=_is_bucket_ready,
            condition=lambda r: r.status_code == http.HTTPStatus.OK,
            retry_count=retry_count,
            backoff_factor=backoff_factor,
        )

        logger.debug("Couchbase container %s is ready.", container.name)
        return container

    except Exception as e:
        container.remove(force=True)
        raise e


def _stop_couchbase(container: docker.models.containers.Container):
    logger.debug("Stopping Couchbase container %s.", container.name)
    container.remove(force=True)

    # We'll keep this sleep here to account for the time it takes for the container to be removed.
    time.sleep(3)


# Fixture to start a Couchbase server instance via Docker (and subsequently remove this instance).
@pytest.fixture
def get_isolated_server() -> docker.models.containers.Container:
    container = None
    try:
        os.environ["AGENT_CATALOG_CONN_STRING"] = DEFAULT_COUCHBASE_CONN_STRING
        os.environ["AGENT_CATALOG_USERNAME"] = DEFAULT_COUCHBASE_USERNAME
        os.environ["AGENT_CATALOG_PASSWORD"] = DEFAULT_COUCHBASE_PASSWORD

        # Enter our test.
        container = _start_couchbase()
        yield container

    # Execute our cleanup.
    finally:
        if container:
            _stop_couchbase(container)
