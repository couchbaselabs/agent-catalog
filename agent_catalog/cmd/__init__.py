import agent_catalog_cmd.cmds

clean = agent_catalog_cmd.cmds.cmd_clean
env = agent_catalog_cmd.cmds.cmd_env
find = agent_catalog_cmd.cmds.cmd_find
index = agent_catalog_cmd.cmds.cmd_index
publish = agent_catalog_cmd.cmds.cmd_publish
status = agent_catalog_cmd.cmds.cmd_status
version = agent_catalog_cmd.cmds.cmd_version

__all__ = ["clean", "env", "find", "index", "publish", "status", "version"]
