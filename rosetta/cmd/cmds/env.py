import json

import flask


blueprint = flask.Blueprint('env', __name__)

@blueprint.route('/env')
def route_env():
    return flask.jsonify(flask.current_app.config['ctx'])


def cmd_env(ctx):
    print(json.dumps(ctx, sort_keys=True, indent=4))

