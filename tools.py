"""Tools the agents can call.

The web_search tool uses Tavily if TAVILY_API_KEY is set; otherwise it returns a
clear signal so the Researcher agent falls back to its own knowledge. This keeps
the demo runnable with only an ANTHROPIC_API_KEY, while showing real tool-use
when a search key is provided.
"""
import os

# Anthropic tool schema advertised to the Researcher agent.
WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current, factual information. Use for anything time-sensitive, "
        "statistical, or that benefits from up-to-date sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."}
        },
        "required": ["query"],
    },
}


def web_search(query: str) -> str:
    """Return search results as text, or a fallback note if no key is configured."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return (
            "web_search is not configured (no TAVILY_API_KEY). "
            "Answer from your own knowledge and note that it may not be current."
        )
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        resp = client.search(query=query, max_results=3)
        lines = []
        for r in resp.get("results", []):
            lines.append(f"- {r.get('title', '')}: {r.get('content', '')} ({r.get('url', '')})")
        return "\n".join(lines) or "No results found."
    except Exception as exc:
        return f"web_search failed: {exc}. Answer from your own knowledge instead."


def build_research_tools():
    """Return (tool_schemas, tool_fns) for the Researcher agent.

    Only advertise the web_search tool when a TAVILY_API_KEY is set. Without a key
    there is nothing to search, so we return no tools — the agents answer from their
    own knowledge in a single call instead of looping on a dead tool.
    """
    if not os.getenv("TAVILY_API_KEY"):
        return [], {}
    return [WEB_SEARCH_TOOL], {"web_search": web_search}
