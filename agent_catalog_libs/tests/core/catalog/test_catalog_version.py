import pytest
import semantic_version

from agent_catalog_libs.core.catalog.version import lib_version_compare
from agent_catalog_libs.core.catalog.version import lib_version_parse


def test_semantic_version():
    assert semantic_version.Version("0.2.0") is not None
    assert semantic_version.Version("0.2.0-alpha") is not None
    assert semantic_version.Version("0.2.0-alpha-foo") is not None
    assert semantic_version.Version("0.2.0-alpha-foo-bar") is not None
    with pytest.raises(ValueError):
        semantic_version.Version("v0.2.0")


@pytest.mark.smoke
def test_lib_version_parse():
    branch, num_commits, hsh = lib_version_parse("v0.2.0-0-g6f9305e")
    assert branch == "v0.2.0"
    assert num_commits == 0
    assert hsh == "g6f9305e"

    branch, num_commits, hsh = lib_version_parse("v0.1.0-55-g8397417")
    assert branch == "v0.1.0"
    assert num_commits == 55
    assert hsh == "g8397417"


def test_lib_version_parse_with_hyphenated_branch_name():
    branch, num_commits, hsh = lib_version_parse("v0.1.0-alpha-4-g6f9305e")
    assert branch == "v0.1.0-alpha"
    assert num_commits == 4
    assert hsh == "g6f9305e"

    branch, num_commits, hsh = lib_version_parse("v0.1.0-beta2-17-gf63950e")
    assert branch == "v0.1.0-beta2"
    assert num_commits == 17
    assert hsh == "gf63950e"

    branch, num_commits, hsh = lib_version_parse("v0.1.0-MB-1234-5-g269f05e")
    assert branch == "v0.1.0-MB-1234"
    assert num_commits == 5
    assert hsh == "g269f05e"


@pytest.mark.smoke
def test_invalid_lib_version_format():
    with pytest.raises(ValueError):
        lib_version_parse("invalid-version-string")
    with pytest.raises(ValueError):
        lib_version_parse("")


def test_missing_v_prefix():
    branch, num_commits, hsh = lib_version_parse("0.2.0-0-g6f9305e")
    assert branch == "0.2.0"
    assert num_commits == 0
    assert hsh == "g6f9305e"


@pytest.mark.smoke
def test_equal_versions():
    assert lib_version_compare("1.0.0-0-g123", "1.0.0-0-g123") == 0


@pytest.mark.smoke
def test_greater_version():
    assert lib_version_compare("1.0.1-0-g123", "1.0.0-0-g123") > 0
    assert lib_version_compare("1.1.1-0-g123", "1.1.0-0-g123") > 0
    assert lib_version_compare("2.1.1-0-g123", "2.1.0-0-g123") > 0
    assert lib_version_compare("20.1.0-0-g123", "9.1.0-0-g123") > 0


@pytest.mark.smoke
def test_lesser_version():
    assert lib_version_compare("1.0.0-0-g123", "1.0.1-0-g123") < 0
    assert lib_version_compare("1.1.0-0-g123", "1.1.1-0-g123") < 0
    assert lib_version_compare("2.0.0-0-g123", "2.0.1-0-g123") < 0
    assert lib_version_compare("9.0.0-0-g123", "20.0.0-0-g123") < 0


def test_with_hyphenated_branch():
    assert lib_version_compare("1.0.0-aaa-0-g123", "1.0.0-0-g123") < 0
    assert lib_version_compare("1.0.0-alpha-0-g123", "1.0.0-0-g123") < 0
    assert lib_version_compare("1.0.0-beta-0-g123", "1.0.0-alpha-0-g123") > 0
    assert lib_version_compare("1.0.0-alpha-0-g123", "1.0.0-beta-0-g123") < 0
    assert lib_version_compare("1.0.0-alpha1-0-g123", "1.0.0-alpha2-0-g123") < 0
