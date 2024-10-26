import pytest

from agentc_testing.server import get_isolated_server

# This is to keep ruff from falsely flagging this as unused.
_ = get_isolated_server


@pytest.mark.skip
@pytest.mark.smoke
def test_local_auditor(tmp_path):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_db_auditor(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_auditor(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.smoke
def test_local_auditor_no_tools(tmp_path):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_db_auditor_no_tools(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_auditor_no_tools(tmp_path, get_isolated_server):
    # TODO (GLENN): Finish me!
    pass
