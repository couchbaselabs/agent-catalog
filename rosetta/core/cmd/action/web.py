import importlib.resources

import flask

def cmd_web(host_port, debug=True):
    app = flask.Flask(__name__)

    from rosetta.core.cmd.action import register_blueprints

    register_blueprints(app)

    host, port = host_port.split(':')

    app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    cmd_web()
