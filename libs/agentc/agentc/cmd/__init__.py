import agentc_cli.cmds

add = agentc_cli.cmds.cmd_add
clean = agentc_cli.cmds.cmd_clean
env = agentc_cli.cmds.cmd_env
find = agentc_cli.cmds.cmd_find
index = agentc_cli.cmds.cmd_index
init = agentc_cli.cmds.cmd_init
ls = agentc_cli.cmds.cmd_ls
publish = agentc_cli.cmds.cmd_publish
status = agentc_cli.cmds.cmd_status
version = agentc_cli.cmds.cmd_version
execute = agentc_cli.cmds.cmd_execute

__all__ = ["add", "clean", "env", "find", "index", "init", "ls", "publish", "status", "version", "execute"]
