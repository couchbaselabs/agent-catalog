import pytest
import semantic_version

from agentc_core.catalog.version import lib_version_parse


def test_semantic_version():
    assert semantic_version.Version("0.2.0") is not None
    assert semantic_version.Version("0.2.0-alpha") is not None
    assert semantic_version.Version("0.2.0-alpha-foo") is not None
    assert semantic_version.Version("0.2.0-alpha-foo-bar") is not None
    with pytest.raises(ValueError):
        semantic_version.Version("v0.2.0")


@pytest.mark.smoke
def test_pep440_version():
    v1 = lib_version_parse("0.2.0")
    assert v1.release == (0, 2, 0)
    assert not v1.is_postrelease

    v2 = lib_version_parse("0.2.0.post1")
    assert v2.release == (0, 2, 0)
    assert v2.is_postrelease
    assert v2.post == 1
