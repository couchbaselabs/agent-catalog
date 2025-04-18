import os

from agentc.catalog import tool
from langchain_experimental.utilities import PythonREPL
from serpapi import GoogleSearch


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


serpapi_params = {"engine": "google", "api_key": os.getenv("SERPAPI_KEY")}


@tool
def web_search(query: str) -> str:
    """Finds general knowledge information using Google search. Can also be used
    to augment more 'general' knowledge to a previous specialist query."""

    search = GoogleSearch({**serpapi_params, "q": query, "num": 5})
    results = search.get_dict()["organic_results"]
    contexts = "\n---\n".join(["\n".join([x["title"], x["snippet"], x["link"]]) for x in results])
    return contexts
