import couchbase.exceptions
import datetime
import logging
import pytest

from agentc_core.activity.logger import ChainLogger
from agentc_core.activity.logger import DBLogger
from agentc_core.activity.models.content import SystemContent
from agentc_core.version import VersionDescriptor


class _FailingCollection:
    """A collection whose insert always raises the given (transient) Couchbase error."""

    def __init__(self, exception: Exception):
        self.exception = exception
        self.attempts = 0

    def insert(self, *args, **kwargs):
        self.attempts += 1
        raise self.exception


class _RecordingCollection:
    def __init__(self):
        self.documents = dict()

    def insert(self, key, value, *args, **kwargs):
        self.documents[key] = value


def _db_logger(collection) -> DBLogger:
    # Note: we bypass __init__ here to avoid requiring a live cluster for these tests.
    db_logger = DBLogger.__new__(DBLogger)
    db_logger.catalog_version = VersionDescriptor(
        is_dirty=False,
        identifier="my_catalog_version",
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    db_logger.annotations = dict()
    db_logger.cb_coll = collection
    db_logger.ttl = datetime.timedelta(seconds=100)
    db_logger.dropped_log_count = 0
    return db_logger


class _RecordingLocalLogger:
    def __init__(self, catalog_version: VersionDescriptor):
        self.catalog_version = catalog_version
        self.annotations = dict()
        self.records = list()

    def _accept(self, log_obj, log_json):
        self.records.append(log_json)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "exception",
    [
        couchbase.exceptions.TimeoutException("timed out"),
        couchbase.exceptions.UnAmbiguousTimeoutException("unambiguous timeout"),
        couchbase.exceptions.TemporaryFailException("temporary failure"),
        couchbase.exceptions.DocumentExistsException("already exists"),
    ],
)
def test_db_logger_swallows_couchbase_errors(exception: Exception, caplog: pytest.LogCaptureFixture):
    collection = _FailingCollection(exception)
    db_logger = _db_logger(collection)

    with caplog.at_level(logging.WARNING, logger="agentc_core.activity.logger.db"):
        # A failed write must not propagate into the calling agent...
        message = db_logger.log(
            content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session"
        )

    # ...but it must be recorded (both in our warning log and in our dropped-record count).
    assert collection.attempts == 1
    assert message.content.value == "Hello world!"
    assert db_logger.dropped_log_count == 1
    assert any(message.identifier in r.getMessage() for r in caplog.records)


@pytest.mark.smoke
def test_db_logger_records_repeated_failures():
    db_logger = _db_logger(_FailingCollection(couchbase.exceptions.TimeoutException("timed out")))
    for _ in range(3):
        db_logger.log(content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session")
    assert db_logger.dropped_log_count == 3


@pytest.mark.smoke
def test_db_logger_does_not_swallow_non_couchbase_errors():
    class _ExplodingCollection:
        def insert(self, *args, **kwargs):
            raise RuntimeError("this is a bug, not a transient cluster error")

    db_logger = _db_logger(_ExplodingCollection())
    with pytest.raises(RuntimeError):
        db_logger.log(content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session")


@pytest.mark.smoke
def test_db_logger_writes_on_healthy_cluster():
    collection = _RecordingCollection()
    db_logger = _db_logger(collection)
    message = db_logger.log(content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session")
    assert list(collection.documents.keys()) == [message.identifier]
    assert collection.documents[message.identifier]["content"]["value"] == "Hello world!"
    assert db_logger.dropped_log_count == 0


@pytest.mark.smoke
def test_chain_logger_writes_locally_when_cluster_fails():
    db_logger = _db_logger(_FailingCollection(couchbase.exceptions.TimeoutException("timed out")))
    local_logger = _RecordingLocalLogger(db_logger.catalog_version)
    chain_logger = ChainLogger(local_logger=local_logger, db_logger=db_logger)

    message = chain_logger.log(
        content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session"
    )

    # The local (durable) copy must survive a failing cluster.
    assert len(local_logger.records) == 1
    assert local_logger.records[0]["identifier"] == message.identifier
    assert db_logger.dropped_log_count == 1


@pytest.mark.smoke
def test_chain_logger_writes_to_both_sinks():
    collection = _RecordingCollection()
    db_logger = _db_logger(collection)
    local_logger = _RecordingLocalLogger(db_logger.catalog_version)
    chain_logger = ChainLogger(local_logger=local_logger, db_logger=db_logger)

    message = chain_logger.log(
        content=SystemContent(value="Hello world!"), span_name=["my_span"], session_id="my_session"
    )
    assert len(local_logger.records) == 1
    assert list(collection.documents.keys()) == [message.identifier]
