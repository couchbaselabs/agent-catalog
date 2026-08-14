import json
import pytest
import requests
import unittest.mock

from agentc_core.config import Config
from agentc_core.remote.util.ddl import get_fts_nodes_hostname
from agentc_core.remote.util.ddl import is_fts_index_present


@pytest.fixture
def cfg():
    return Config(
        conn_string="couchbase://localhost",
        username="Administrator",
        password="password",
        bucket="travel-sample",
    )


def _response(status_code=200, text=""):
    response = unittest.mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


@pytest.mark.smoke
def test_is_fts_index_present_returns_index_def_on_ok(cfg):
    index_def = {"name": "my_index"}
    body = json.dumps({"status": "ok", "indexDefs": {"indexDefs": {"my_index": index_def}}})
    with unittest.mock.patch("requests.request", return_value=_response(text=body)):
        result, err = is_fts_index_present(cfg, "my_index", ["node1"])
    assert err is None
    assert result == index_def


@pytest.mark.smoke
def test_is_fts_index_present_returns_false_when_index_missing(cfg):
    body = json.dumps({"status": "ok", "indexDefs": {"indexDefs": {"other_index": {}}}})
    with unittest.mock.patch("requests.request", return_value=_response(text=body)):
        result, err = is_fts_index_present(cfg, "my_index", ["node1"])
    assert err is None
    assert result is False


@pytest.mark.smoke
def test_is_fts_index_present_retries_next_node_on_connection_error(cfg):
    body = json.dumps({"status": "ok", "indexDefs": None})
    with unittest.mock.patch(
        "requests.request",
        side_effect=[requests.exceptions.ConnectionError("node1 is down"), _response(text=body)],
    ) as mock_request:
        result, err = is_fts_index_present(cfg, "my_index", ["node1", "node2"])
    assert err is None
    assert result is False
    assert mock_request.call_count == 2


@pytest.mark.smoke
def test_is_fts_index_present_returns_error_on_malformed_response(cfg):
    with unittest.mock.patch("requests.request", return_value=_response(text="not json")):
        result, err = is_fts_index_present(cfg, "my_index", ["node1"])
    assert result is False
    assert isinstance(err, ValueError)


@pytest.mark.smoke
def test_is_fts_index_present_returns_error_when_status_not_ok(cfg):
    body = json.dumps({"status": "fail"})
    with unittest.mock.patch("requests.request", return_value=_response(text=body)):
        result, err = is_fts_index_present(cfg, "my_index", ["node1"])
    assert result is False
    assert isinstance(err, RuntimeError)


@pytest.mark.smoke
def test_is_fts_index_present_returns_error_when_all_nodes_down(cfg):
    with unittest.mock.patch("requests.request", side_effect=requests.exceptions.ConnectionError("down")):
        result, err = is_fts_index_present(cfg, "my_index", ["node1", "node2"])
    assert result is False
    assert isinstance(err, RuntimeError)


@pytest.mark.smoke
def test_get_fts_nodes_hostname_returns_nodes_on_ok(cfg):
    body = json.dumps(
        {
            "name": "default",
            "nodes": [
                {"services": ["fts", "kv"], "configuredHostname": "node1:8091"},
                {"services": ["kv"], "configuredHostname": "node2:8091"},
            ],
        }
    )
    with unittest.mock.patch("requests.request", return_value=_response(text=body)):
        nodes, err = get_fts_nodes_hostname(cfg)
    assert err is None
    assert nodes == ["node1"]


@pytest.mark.smoke
def test_get_fts_nodes_hostname_returns_connection_error(cfg):
    with unittest.mock.patch("requests.request", side_effect=requests.exceptions.ConnectionError("host is down")):
        nodes, err = get_fts_nodes_hostname(cfg)
    assert nodes is None
    assert isinstance(err, requests.exceptions.ConnectionError)


@pytest.mark.smoke
def test_get_fts_nodes_hostname_returns_error_on_malformed_response(cfg):
    with unittest.mock.patch("requests.request", return_value=_response(text="not json")):
        nodes, err = get_fts_nodes_hostname(cfg)
    assert nodes is None
    assert isinstance(err, ValueError)
