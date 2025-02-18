import pytest

from agentc_testing.server import isolated_server_factory

# This is to keep ruff from falsely flagging this as unused.
_ = isolated_server_factory


@pytest.mark.skip
@pytest.mark.smoke
def test_local_auditor(tmp_path):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_db_auditor(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_auditor(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.smoke
def test_local_auditor_no_tools(tmp_path):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_db_auditor_no_tools(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass


@pytest.mark.skip
@pytest.mark.regression
def test_chain_auditor_no_tools(tmp_path, isolated_server_factory):
    # TODO (GLENN): Finish me!
    pass
