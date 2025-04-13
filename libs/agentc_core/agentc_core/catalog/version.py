import packaging.version
import semantic_version

from .. import __version__ as LIB_VERSION


def lib_version():
    # These versions should be PEP 440 compatible:
    # https://packaging.python.org/en/latest/specifications/version-specifiers/#version-scheme
    return LIB_VERSION


def lib_version_parse(s):
    return packaging.version.parse(s)


def lib_version_compare(s1, s2):
    v1 = lib_version_parse(s1)
    v2 = lib_version_parse(s2)
    if v1 > v2:
        return 1
    if v1 < v2:
        return -1
    return 0


def catalog_schema_version_compare(s1, s2):
    return semantic_version_compare(s1, s2)


def semantic_version_compare(s1, s2):
    v1 = semantic_version.Version(s1)
    v2 = semantic_version.Version(s2)

    if v1 > v2:
        return 1

    if v1 < v2:
        return -1

    return 0
