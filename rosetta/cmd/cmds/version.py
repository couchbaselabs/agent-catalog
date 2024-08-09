from rosetta.core.catalog.version import lib_version

import flask


blueprint = flask.Blueprint('version', __name__)

@blueprint.route('/version')
def route_version():
    return flask.jsonify(lib_version())


def cmd_version(ctx):
    print(lib_version())


if __name__ == "__main__":
    cmd_version({})

