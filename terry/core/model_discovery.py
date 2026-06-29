"""Auto-discover model endpoints from OpenAI-compatible providers.

OpenCode users (+167) want automatic model discovery from any
OpenAI-compatible endpoint. This module probes endpoints and
auto-registers discovered models.

Usage:
    from terry.core.model_discovery import discover_models
    models = discover_models("http://localhost:11434/v1")  # Ollama
    models = discover_models("https://api.openai.com/v1")  # OpenAI
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 10


@dataclass
class DiscoveredModel:
    """A model discovered from an endpoint."""

    id: str
    provider: str = ""
    endpoint: str = ""
    owned_by: str = ""
    context_window: int = 128000
    tier: str = "medium"  # budget, medium, premium

    def to_dict(self) -> dict:
        return {
            "id": self.id, "provider": self.provider,
            "endpoint": self.endpoint, "context_window": self.context_window,
            "tier": self.tier,
        }


def discover_models(
    base_url: str,
    api_key: str = "ollama",  # Ollama doesn't require a real key
    timeout: int = DISCOVERY_TIMEOUT,
) -> list[DiscoveredModel]:
    """Discover available models from an OpenAI-compatible endpoint.

    Works with: Ollama, vLLM, LM Studio, LocalAI, OpenAI, DeepSeek, etc.
    """
    url = base_url.rstrip("/") + "/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())

        models = []
        items = data.get("data", data.get("models", []))
        for item in items:
            model_id = item.get("id", item.get("name", ""))
            if not model_id:
                continue

            tier = _classify_tier(model_id)
            models.append(DiscoveredModel(
                id=model_id,
                provider=_guess_provider(base_url),
                endpoint=base_url,
                owned_by=item.get("owned_by", ""),
                context_window=item.get("context_length", 128000),
                tier=tier,
            ))

        logger.info("Discovered %d models from %s", len(models), base_url)
        return models
    except Exception as e:
        logger.debug("Model discovery failed for %s: %s", base_url, e)
        return []


def _classify_tier(model_id: str) -> str:
    """Classify a model into budget/medium/premium based on its name."""
    lower = model_id.lower()
    budget_keywords = ["tiny", "mini", "small", "nano", "haiku", "flash",
                       "1.5b", "3b", "7b", "8b"]
    premium_keywords = ["large", "premium", "pro", "ultra", "opus",
                        "70b", "405b", "671b"]

    for kw in premium_keywords:
        if kw in lower:
            return "premium"
    for kw in budget_keywords:
        if kw in lower:
            return "budget"
    return "medium"


def _guess_provider(url: str) -> str:
    """Guess the provider name from the endpoint URL."""
    lower = url.lower()
    if "ollama" in lower:
        return "ollama"
    if "openai" in lower:
        return "openai"
    if "deepseek" in lower:
        return "deepseek"
    if "anthropic" in lower:
        return "anthropic"
    if "localhost" in lower or "127.0.0.1" in lower:
        return "local"
    return "custom"
