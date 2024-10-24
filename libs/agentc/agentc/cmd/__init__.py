import agentc_cli.cmds

add = agentc_cli.cmds.cmd_add
clean = agentc_cli.cmds.cmd_clean
env = agentc_cli.cmds.cmd_env
find = agentc_cli.cmds.cmd_find
index = agentc_cli.cmds.cmd_index
publish = agentc_cli.cmds.cmd_publish
status = agentc_cli.cmds.cmd_status
version = agentc_cli.cmds.cmd_version
execute = agentc_cli.cmds.cmd_execute

__all__ = ["add", "clean", "env", "find", "index", "publish", "status", "version", "execute"]
