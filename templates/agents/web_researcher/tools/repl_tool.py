from agentc import tool
from langchain_experimental.utilities import PythonREPL


@tool
def repl_tool(code: str) -> str:
    """Tool to execute python code"""

    repl = PythonREPL()
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"

    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"

    return result_str + "\n\nIf you have completed all tasks, respond with FINAL ANSWER."
