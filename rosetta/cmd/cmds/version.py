import importlib.resources
import re

from semantic_version import Version

import flask

blueprint = flask.Blueprint('version', __name__)

@blueprint.route('/version')
def route_version():
    return flask.jsonify(version())


def cmd_version():
    print(version())


# TODO: Consider grabbing version from the package distribution metadata of rosetta?
# TODO: Consider defaulting to output of `git describe --long --always`?
# TODO: This should probably be moved into rosetta/core?

def version():
    # Ex: "v0.2.0-0-g6f9305e".
    # Ex: "v0.1.0-alpha-4-g6f9305e".
    # Ex: "v0.1.0-beta2-17-gf63950e".
    # Ex: "v0.1.0-cbse1234-5-g269f05e".
    lines = importlib.resources.files('rosetta').joinpath('VERSION.txt').read_text().split('\n')
    return '\n'.join([line for line in lines if not line.startswith('#')]).strip()


def version_parse(s):
    match = re.match(r"^([\d\.\-a-zA-Z]+)-(\d+)-(g[0-9a-f]+)$", s)
    if not match:
        raise ValueError(f"Invalid version format: {s}")

    branch, num_commits, hash = match.groups()

    return branch, int(num_commits), hash


def version_compare(s1, s2):
    branch1, num_commits1, hash1 = version_parse(s1)
    branch2, num_commits2, hash2 = version_parse(s2)

    if branch1 != branch2:
        return None

    if num_commits1 > num_commits2:
        return 1
    if num_commits1 < num_commits2:
        return -1

    return 0


if __name__ == "__main__":
    cmd_version()

