import couchbase.auth
import couchbase.cluster
import couchbase.options
import datetime
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

DEFAULT_COUCHBASE_CONN_STRING = "couchbase://127.0.0.1"
DEFAULT_COUCHBASE_USERNAME = "Administrator"
DEFAULT_COUCHBASE_PASSWORD = "password"
DEFAULT_COUCHBASE_BUCKET = "travel-sample"

# TODO (GLENN): We should move this to a more appropriate location.
os.environ["AGENT_CATALOG_DEBUG"] = "true"


# For whatever reason, the HTTP Retry adapter isn't working for me.
def _execute_with_retry(
    func: typing.Callable,
    condition: typing.Callable[..., bool],
    result_str: typing.Callable[..., str],
    retry_count: int,
    backoff_factor: float = 0.1,
):
    for i in range(retry_count):
        try:
            result = func()
            if condition(result):
                logger.debug(f"Function succeeded with result {result_str(result)}.")
                return result
        except Exception as e:
            logger.debug(f"Function failed with error: {str(e)}")
            if i == retry_count - 1:
                logger.error(f"Function failed after {retry_count} retries.")
                raise e
        time.sleep(backoff_factor * (2**i))


def _start_container(volume_path: pathlib.Path) -> docker.models.containers.Container:
    logger.info("Creating Couchbase container with volume path: %s.", volume_path)
    volume_path.mkdir(exist_ok=True)

    # Start the Couchbase container.
    time.sleep(3)
    client = docker.from_env()
    ports = {f"{port}/tcp": port for port in range(8091, 8098)}
    ports |= {f"{port}/tcp": port for port in range(18091, 18098)}
    ports |= {
        "9123/tcp": 9123,
        "9140/tcp": 9140,
        "11207/tcp": 11207,
        "11210/tcp": 11210,
        "11280/tcp": 11280,
    }
    logger.info("Starting Couchbase container with ports: %s.", ports)
    return client.containers.run(
        image="couchbase",
        name=f"agentc_{uuid.uuid4().hex}",
        ports=ports,
        detach=True,
        remove=True,
        stderr=True,
        volumes={str(volume_path.absolute()): {"bind": "/opt/couchbase/var", "mode": "rw"}},
    )


def _setup_bucket(
    container: docker.models.containers.Container,
    retry_count: int = 5,
    backoff_factor: float = 0.7,
    wait_for_ready: bool = True,
) -> None:
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
        result_str=lambda r: r.text,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )
    if not wait_for_ready:
        return

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
        result_str=lambda r: r.text,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )
    return


def _start_couchbase(
    container: docker.models.containers.Container,
    retry_count: int = 5,
    backoff_factor: float = 0.7,
    wait_for_ready: bool = True,
) -> None:
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
        result_str=lambda r: r.text,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )

    _setup_bucket(container, retry_count, backoff_factor, wait_for_ready)

    # As a sanity check, we should now be able to use our SDK to connect to our cluster.
    def _is_client_ready():
        cluster = couchbase.cluster.Cluster(
            DEFAULT_COUCHBASE_CONN_STRING,
            couchbase.options.ClusterOptions(
                authenticator=couchbase.auth.PasswordAuthenticator(
                    username=DEFAULT_COUCHBASE_USERNAME, password=DEFAULT_COUCHBASE_PASSWORD
                ),
            ),
        )
        cluster.wait_until_ready(datetime.timedelta(seconds=60))
        return cluster.cluster_info()

    logger.info("Checking if SDK can reach our cluster in container %s.", container.name)
    _execute_with_retry(
        func=_is_client_ready,
        condition=lambda _: True,
        result_str=lambda q: q,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )
    logger.debug("Couchbase container %s is ready.", container.name)


def _restart_couchbase(
    container: docker.models.containers.Container,
    retry_count: int = 5,
    backoff_factor: float = 0.7,
    wait_for_ready: bool = True,
) -> None:
    # Drop our bucket...
    def _drop_bucket():
        return requests.delete(
            "http://localhost:8091/pools/default/buckets/travel-sample",
            auth=(DEFAULT_COUCHBASE_USERNAME, DEFAULT_COUCHBASE_PASSWORD),
        )

    logger.info("Dropping previous bucket data (travel-sample)")
    _execute_with_retry(
        func=_drop_bucket,
        condition=lambda r: r.status_code in {http.HTTPStatus.OK},
        result_str=lambda r: r.text,
        retry_count=retry_count,
        backoff_factor=backoff_factor,
    )

    _setup_bucket(container, retry_count, backoff_factor, wait_for_ready)


def _stop_container(container: docker.models.containers.Container):
    logger.info("Stopping Couchbase container %s.", container.name)
    try:
        logger.debug(container.logs())
        container.remove(force=True)

        # We'll keep this sleep here to account for the time it takes for the container to be removed.
        time.sleep(3)

    except Exception as e:
        logger.exception(e, exc_info=True, stack_info=True)


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
    os.environ["AGENT_CATALOG_WAIT_UNTIL_READY_SECONDS"] = "60"
    os.environ["AGENT_CATALOG_DDL_CREATE_INDEX_INTERVAL_SECONDS"] = "30"
    os.environ["AGENT_CATALOG_DDL_RETRY_WAIT_SECONDS"] = "60"

    container_instance = set()
    try:
        # (we need to capture the container we spawn).
        def get_isolated_server(volume_path: pathlib.Path) -> docker.models.containers.Container:
            container = _start_container(volume_path)
            container_instance.add(container)
            _start_couchbase(container)
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
        del os.environ["AGENT_CATALOG_DDL_CREATE_INDEX_INTERVAL_SECONDS"]
        del os.environ["AGENT_CATALOG_DDL_RETRY_WAIT_SECONDS"]
        if len(container_instance) > 0:
            _stop_container(container_instance.pop())


# Fixture to start a Couchbase server instance via Docker (and subsequently remove this instance).
@pytest.fixture(scope="session")
def shared_server_factory(tmp_path_factory) -> typing.Callable[[], docker.models.containers.Container]:
    os.environ["AGENT_CATALOG_CONN_STRING"] = DEFAULT_COUCHBASE_CONN_STRING
    os.environ["AGENT_CATALOG_USERNAME"] = DEFAULT_COUCHBASE_USERNAME
    os.environ["AGENT_CATALOG_PASSWORD"] = DEFAULT_COUCHBASE_PASSWORD
    os.environ["AGENT_CATALOG_BUCKET"] = DEFAULT_COUCHBASE_BUCKET
    os.environ["AGENT_CATALOG_DDL_CREATE_INDEX_INTERVAL_SECONDS"] = "5"
    os.environ["AGENT_CATALOG_DDL_RETRY_WAIT_SECONDS"] = "5"
    container = None

    try:
        container = _start_container(tmp_path_factory.mktemp(".couchbase"))
        _start_couchbase(container)
        skip_token = {1}

        # (we need to capture the container we spawn).
        def get_shared_server() -> docker.models.containers.Container:
            if len(skip_token) == 0:
                _restart_couchbase(container)
            else:
                skip_token.pop()
            return container

        # Enter our test.
        yield get_shared_server

    # Execute our cleanup.
    finally:
        if container is not None:
            _stop_container(container)
        del os.environ["AGENT_CATALOG_CONN_STRING"]
        del os.environ["AGENT_CATALOG_USERNAME"]
        del os.environ["AGENT_CATALOG_PASSWORD"]
        del os.environ["AGENT_CATALOG_BUCKET"]
        del os.environ["AGENT_CATALOG_DDL_CREATE_INDEX_INTERVAL_SECONDS"]
        del os.environ["AGENT_CATALOG_DDL_RETRY_WAIT_SECONDS"]


if __name__ == "__main__":
    import sys
    import tempfile

    os.environ["AGENT_CATALOG_CONN_STRING"] = DEFAULT_COUCHBASE_CONN_STRING
    os.environ["AGENT_CATALOG_USERNAME"] = DEFAULT_COUCHBASE_USERNAME
    os.environ["AGENT_CATALOG_PASSWORD"] = DEFAULT_COUCHBASE_PASSWORD
    os.environ["AGENT_CATALOG_BUCKET"] = DEFAULT_COUCHBASE_BUCKET
    os.environ["AGENT_CATALOG_WAIT_UNTIL_READY_SECONDS"] = "60"
    with tempfile.TemporaryDirectory() as _tmp:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
        _container = _start_container(pathlib.Path(_tmp))
        try:
            _start_couchbase(pathlib.Path(_tmp), wait_for_ready=True)
            print("Couchbase container started. Press Ctrl+C to stop.")
            while True:
                pass

        except KeyboardInterrupt:
            pass

        finally:
            del os.environ["AGENT_CATALOG_CONN_STRING"]
            del os.environ["AGENT_CATALOG_USERNAME"]
            del os.environ["AGENT_CATALOG_PASSWORD"]
            del os.environ["AGENT_CATALOG_BUCKET"]
            del os.environ["AGENT_CATALOG_WAIT_UNTIL_READY_SECONDS"]
            _stop_container(_container)
