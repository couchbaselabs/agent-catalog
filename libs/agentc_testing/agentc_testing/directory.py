import _pytest.tmpdir
import pathlib
import pytest
import shutil
import typing


# Note: this is a fixture that is meant to replace tmp_path. Right now, tmp_path and pytest-retry do not play well.
@pytest.fixture
def temporary_directory(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> typing.Generator[pathlib.Path, None, None]:
    path = _pytest.tmpdir._mk_tmp(request, tmp_path_factory)
    yield path

    # Remove the tmpdir if the policy is "failed" and the test passed.
    tmp_path_factory: pytest.TempPathFactory = request.session.config._tmp_path_factory  # type: ignore
    policy = tmp_path_factory._retention_policy
    result_dict = request.node.stash[_pytest.tmpdir.tmppath_result_key]

    if policy == "failed" and result_dict.get("call", True):
        # We do a "best effort" to remove files, but it might not be possible due to some leaked resource,
        # permissions, etc, in which case we ignore it.
        shutil.rmtree(path, ignore_errors=True)

    # Do not remove this fixture from the stash (this is the change).
    # del request.node.stash[tmppath_result_key]
