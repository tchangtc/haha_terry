"""Custom search provider registry — pluggable web search backends.

Hermes users (+30) want Searxng support. This lets users configure
any search backend: Google, Bing, Searxng, Tavily, Firecrawl, etc.

Usage:
    from terry.core.search_providers import SearchProviderRegistry
    reg = SearchProviderRegistry()
    reg.register("searxng", "https://searx.example.com/search?q={query}")
    reg.set_default("searxng")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class SearchProvider:
    """A search backend configuration."""

    name: str
    url_template: str  # e.g. "https://searx.example.com/search?q={query}"
    api_key: str = ""
    headers: dict = field(default_factory=dict)
    description: str = ""
    enabled: bool = True

    def build_url(self, query: str) -> str:
        return self.url_template.replace("{query}", quote(query))

    def to_dict(self) -> dict:
        return {
            "name": self.name, "url_template": self.url_template,
            "description": self.description, "enabled": self.enabled,
        }


# Built-in providers
BUILTIN_PROVIDERS: dict[str, SearchProvider] = {
    "duckduckgo": SearchProvider(
        name="duckduckgo",
        url_template="https://html.duckduckgo.com/html/?q={query}",
        description="DuckDuckGo — privacy-focused search (default)",
    ),
    "google": SearchProvider(
        name="google",
        url_template="https://www.google.com/search?q={query}",
        description="Google search (requires API key for structured results)",
    ),
    "searxng": SearchProvider(
        name="searxng",
        url_template="https://searx.be/search?q={query}&format=json",
        description="Searxng — self-hosted, privacy-respecting metasearch",
    ),
}


class SearchProviderRegistry:
    """Manage and switch between search backends."""

    def __init__(self):
        self._providers: dict[str, SearchProvider] = dict(BUILTIN_PROVIDERS)
        self._default = "duckduckgo"
        self._load_user_providers()

    def _load_user_providers(self):
        from terry.core.platform_utils import get_terry_dir
        path = get_terry_dir() / "search_providers.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                for p in data.get("providers", []):
                    self._providers[p["name"]] = SearchProvider(**p)
                self._default = data.get("default", self._default)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

    def _save(self):
        from terry.core.platform_utils import get_terry_dir
        path = get_terry_dir() / "search_providers.json"
        data = {
            "providers": [p.to_dict() for p in self._providers.values()
                          if p.name not in BUILTIN_PROVIDERS],
            "default": self._default,
        }
        path.write_text(json.dumps(data, indent=2))

    def register(self, name: str, url_template: str, description: str = "",
                 api_key: str = ""):
        """Register a custom search provider."""
        self._providers[name] = SearchProvider(
            name=name, url_template=url_template,
            description=description, api_key=api_key,
        )
        self._save()

    def remove(self, name: str):
        """Remove a custom search provider (built-ins cannot be removed)."""
        if name in BUILTIN_PROVIDERS:
            raise ValueError(f"Cannot remove built-in provider: {name}")
        self._providers.pop(name, None)
        if self._default == name:
            self._default = "duckduckgo"
        self._save()

    def set_default(self, name: str):
        """Set the default search provider."""
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        self._default = name
        self._save()

    def get_default(self) -> SearchProvider:
        return self._providers.get(self._default, BUILTIN_PROVIDERS["duckduckgo"])

    def get(self, name: str) -> SearchProvider | None:
        return self._providers.get(name)

    def list_all(self) -> list[SearchProvider]:
        return list(self._providers.values())

    def search_url(self, query: str, provider: str | None = None) -> str:
        """Build a search URL for the given query."""
        p = self.get(provider or self._default)
        if p is None:
            p = BUILTIN_PROVIDERS["duckduckgo"]
        return p.build_url(query)

    def get_stats(self) -> dict:
        custom = [n for n in self._providers if n not in BUILTIN_PROVIDERS]
        return {
            "total_providers": len(self._providers),
            "default": self._default,
            "custom": custom,
        }
