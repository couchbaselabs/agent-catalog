import importlib.resources

import flask

blueprint = flask.Blueprint('version', __name__)

@blueprint.route('/version')
def route_version():
    return flask.jsonify(version())

def cmd_version():
    print(version())

def version():
    lines = importlib.resources.files('rosetta').joinpath('VERSION.txt').read_text().split('\n')
    return '\n'.join([line for line in lines if not line.startswith('#')]).strip()

if __name__ == "__main__":
    cmd_version()
