import flask


def cmd_web(ctx, host_port, debug=True):
    app = flask.Flask(__name__)

    app.config['ctx'] = ctx

    from rosetta.cmd.cmds import register_blueprints

    register_blueprints(app)

    a = host_port.split(':')
    if len(a) >= 2:
        host, port = a[0], a[-1] # Ex: "127.0.0.1:5555"
    else:
        host, port = "127.0.0.1", a[-1] # Ex: "5555".

    app.run(host=host, port=port, debug=debug)
