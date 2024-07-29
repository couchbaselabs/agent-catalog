import importlib.resources

import flask

def cmd_web():
    app = flask.Flask(__name__)

    from rosetta.core.cmd.action import register_blueprints

    register_blueprints(app)

    # TODO: Allow configurable HOST, PORT, etc.
    app.run(host='0.0.0.0', port=5555, debug=True)

if __name__ == "__main__":
    cmd_web()
