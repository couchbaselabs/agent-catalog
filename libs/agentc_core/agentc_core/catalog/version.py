import re
import semantic_version
import subprocess

from .. import __version__ as LIB_VERSION


def lib_version():
    # Ex: "v0.2.0-0-g6f9305e".
    # Ex: "v0.1.0-alpha-4-g6f9305e".
    # Ex: "v0.1.0-beta2-17-gf63950e".
    # Ex: "v0.1.0-cbse1234-5-g269f05e".
    v = LIB_VERSION
    if v == "vMajor.Minor.Micro-N-GITSHA":
        return "v0.0.0-0-g0"

        # TODO: BUG: This does not work unless we're in agentc_core.

        # Default to output of `git describe --long --always`.
        v = (
            subprocess.check_output(["git", "describe", "--long", "--always"], stderr=subprocess.STDOUT)
            .decode("utf-8")
            .strip()
        )

    return v


def lib_version_parse(s):
    match = re.match(r"^([\d\.\-a-zA-Z]+)-(\d+)-(g[0-9a-f]+)$", s)
    if match:
        branch, num_commits, hash = match.groups()

        return branch, int(num_commits), hash

    raise ValueError(f"Invalid lib version format: {s}")


def lib_version_compare(s1, s2):
    branch1, num_commits1, hash1 = lib_version_parse(s1)
    branch2, num_commits2, hash2 = lib_version_parse(s2)

    if branch1 == branch2:
        if num_commits1 > num_commits2:
            return 1

        if num_commits1 < num_commits2:
            return -1

        return 0

    if branch1.startswith("v"):  # Slice off initial "v", from "v0.0.0" to "0.0.0".
        branch1 = branch1[1:]

    if branch2.startswith("v"):
        branch2 = branch2[1:]

    return semantic_version_compare(branch1, branch2)


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
