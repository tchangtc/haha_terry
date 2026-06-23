"""Web search tool - search the web for information."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from . import BaseTool, tool_registry


class WebSearchTool(BaseTool):
    """Search the web for information."""
    risk_level = "read_only"
    category = "web"

    name = "web_search"
    description = "Search the web for current information. Returns search results with titles, URLs, and snippets."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.api_key = os.environ.get("SERPER_API_KEY") or os.environ.get("GOOGLE_SEARCH_API_KEY")

    def execute(self, query: str, num_results: int = 5) -> str:
        """Execute web search.

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            Formatted search results
        """
        if not self.api_key:
            return "Error: Web search requires SERPER_API_KEY or GOOGLE_SEARCH_API_KEY environment variable"

        num_results = min(num_results, 10)  # Cap at 10 results

        try:
            # Use Serper.dev API (Google Search API)
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "q": query,
                        "num": num_results,
                    },
                )
                response.raise_for_status()

            data = response.json()

            # Format results
            results = []
            results.append(f"Search results for: {query}\n")

            # Organic results
            if "organic" in data:
                for i, result in enumerate(data["organic"][:num_results], 1):
                    title = result.get("title", "No title")
                    link = result.get("link", "")
                    snippet = result.get("snippet", "No description")

                    results.append(f"{i}. **{title}**")
                    results.append(f"   URL: {link}")
                    results.append(f"   {snippet}")
                    results.append("")

            # Knowledge graph (if available)
            if "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                results.append("### Knowledge Graph")
                if "title" in kg:
                    results.append(f"**{kg['title']}**")
                if "type" in kg:
                    results.append(f"Type: {kg['type']}")
                if "description" in kg:
                    results.append(f"{kg['description']}")
                results.append("")

            # Answer box (if available)
            if "answerBox" in data:
                ab = data["answerBox"]
                results.append("### Quick Answer")
                if "answer" in ab:
                    results.append(ab["answer"])
                elif "snippet" in ab:
                    results.append(ab["snippet"])
                results.append("")

            if len(results) == 1:  # Only the header, no results
                return f"No search results found for: {query}"

            return "\n".join(results)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(WebSearchTool())
