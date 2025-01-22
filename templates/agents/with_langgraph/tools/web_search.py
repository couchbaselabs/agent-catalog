import os

from agentc import tool
from serpapi import GoogleSearch

serpapi_params = {"engine": "google", "api_key": os.getenv("SERPAPI_KEY")}


@tool()
def web_search(query: str) -> str:
    """Finds general knowledge information using Google search. Can also be used
    to augment more 'general' knowledge to a previous specialist query."""

    search = GoogleSearch({**serpapi_params, "q": query, "num": 5})
    results = search.get_dict()["organic_results"]
    contexts = "\n---\n".join(["\n".join([x["title"], x["snippet"], x["link"]]) for x in results])
    return contexts
