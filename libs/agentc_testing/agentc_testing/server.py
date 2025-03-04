import couchbase.auth
import couchbase.cluster
import couchbase.options
import docker
import docker.models.containers
import http
import logging
import os
import pathlib
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
DEFAULT_COUCHBASE_BUCKET = "travel-sample"

# TODO (GLENN): We should move this to a more appropriate location.
os.environ["AGENT_CATALOG_DEBUG"] = "true"


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


def _start_couchbase(
    volume_path: pathlib.Path, retry_count: int = 5, backoff_factor: float = 0.7
) -> docker.models.containers.Container:
    logger.info("Creating Couchbase container with volume path: %s.", volume_path)
    volume_path.mkdir(exist_ok=True)

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
    logger.info("Starting Couchbase container with ports: %s.", ports)
    container: docker.models.containers.Container = client.containers.run(
        image="couchbase",
        name=f"agentc_{uuid.uuid4().hex}",
        ports=ports,
        detach=True,
        auto_remove=True,
        remove=True,
        volumes={str(volume_path.absolute()): {"bind": "/opt/couchbase/var", "mode": "rw"}},
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

        logger.info("Initializing Couchbase container %s (clusterInit).", container.name)
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

        logger.info("Installing travel-sample bucket in Couchbase container %s.", container.name)
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

        logger.info("Waiting for travel-sample bucket to be ready in Couchbase container %s.", container.name)
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
    logger.info("Stopping Couchbase container %s.", container.name)
    container.remove(force=True)

    # We'll keep this sleep here to account for the time it takes for the container to be removed.
    time.sleep(3)


@pytest.fixture
def connection_factory() -> typing.Callable[[], couchbase.cluster.Cluster]:
    return lambda: couchbase.cluster.Cluster(
        DEFAULT_COUCHBASE_CONN_STRING,
        couchbase.options.ClusterOptions(
            couchbase.auth.PasswordAuthenticator(
                username=DEFAULT_COUCHBASE_USERNAME, password=DEFAULT_COUCHBASE_PASSWORD
            )
        ),
    )


# Fixture to start a Couchbase server instance via Docker (and subsequently remove this instance).
@pytest.fixture
def isolated_server_factory() -> typing.Callable[[pathlib.Path], docker.models.containers.Container]:
    os.environ["AGENT_CATALOG_CONN_STRING"] = DEFAULT_COUCHBASE_CONN_STRING
    os.environ["AGENT_CATALOG_USERNAME"] = DEFAULT_COUCHBASE_USERNAME
    os.environ["AGENT_CATALOG_PASSWORD"] = DEFAULT_COUCHBASE_PASSWORD
    os.environ["AGENT_CATALOG_BUCKET"] = DEFAULT_COUCHBASE_BUCKET
    os.environ["AGENT_CATALOG_WAIT_UNTIL_READY_SECONDS"] = "30"

    container_instance = set()
    try:
        # (we need to capture the container we spawn).
        def get_isolated_server(volume_path: pathlib.Path) -> docker.models.containers.Container:
            container = _start_couchbase(volume_path)
            container_instance.add(container)
            return container

        # Enter our test.
        yield get_isolated_server

    # Execute our cleanup.
    finally:
        del os.environ["AGENT_CATALOG_CONN_STRING"]
        del os.environ["AGENT_CATALOG_USERNAME"]
        del os.environ["AGENT_CATALOG_PASSWORD"]
        del os.environ["AGENT_CATALOG_BUCKET"]
        del os.environ["AGENT_CATALOG_WAIT_UNTIL_READY_SECONDS"]
        if len(container_instance) > 0:
            _stop_couchbase(container_instance.pop())


if __name__ == "__main__":
    import tempfile

    os.environ["AGENT_CATALOG_CONN_STRING"] = DEFAULT_COUCHBASE_CONN_STRING
    os.environ["AGENT_CATALOG_USERNAME"] = DEFAULT_COUCHBASE_USERNAME
    os.environ["AGENT_CATALOG_PASSWORD"] = DEFAULT_COUCHBASE_PASSWORD
    with tempfile.TemporaryDirectory() as _tmp:
        try:
            _container = _start_couchbase(pathlib.Path(_tmp))
            print("Couchbase container started. Press Ctrl+C to stop.")
            while True:
                pass

        except KeyboardInterrupt:
            pass

        finally:
            del os.environ["AGENT_CATALOG_CONN_STRING"]
            del os.environ["AGENT_CATALOG_USERNAME"]
            del os.environ["AGENT_CATALOG_PASSWORD"]
            _stop_couchbase(_container)
