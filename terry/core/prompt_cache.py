"""Prompt caching utilities for reducing LLM API costs.

Implements cache-aware system prompt construction and cache-break
point placement to maximize Anthropic prompt cache hit rates.
"""

from __future__ import annotations

from typing import Any


class PromptCache:
    """Utilities for maximizing LLM prompt cache utilization.

    Anthropic's prompt cache has a 5-minute TTL and caches the
    prefix of the prompt. By placing static content (system prompt,
    tool definitions) at the beginning and marking cache break points,
    we maximize cache hits.
    """

    # Minimum characters to cache (Anthropic: 1024 tokens ≈ 4096 chars)
    MIN_CACHE_CHARS = 4096

    # Maximum cacheable prefix (depends on model)
    MAX_CACHE_TOKENS = {
        "claude-sonnet-4-20250514": 160_000,
        "claude-3-5-sonnet-20241022": 160_000,
        "claude-3-opus-20240229": 160_000,
        "claude-3-haiku-20240307": 160_000,
    }

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._hits = 0
        self._misses = 0
        self._savings_estimate = 0.0

    def should_cache(self, content: str) -> bool:
        """Check if content is long enough to benefit from caching."""
        return len(content) >= self.MIN_CACHE_CHARS

    def build_cacheable_prompt(
        self,
        system: str,
        tool_definitions: list[dict],
        static_context: str = "",
    ) -> list[dict]:
        """Build a prompt designed to maximize cache hits.

        Returns a list of content blocks with cache_control markers
        where appropriate.
        """
        blocks = []

        # Block 1: System prompt (cacheable)
        if system:
            blocks.append({
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            })

        # Block 2: Tool definitions (cacheable if > MIN_CACHE_CHARS)
        if tool_definitions:
            tools_text = self._format_tools(tool_definitions)
            tool_block = {
                "type": "text",
                "text": f"<tools>\n{tools_text}\n</tools>",
            }
            if len(tools_text) >= self.MIN_CACHE_CHARS:
                tool_block["cache_control"] = {"type": "ephemeral"}
            blocks.append(tool_block)

        # Block 3: Static context (cacheable)
        if static_context:
            ctx_block = {"type": "text", "text": static_context}
            if len(static_context) >= self.MIN_CACHE_CHARS:
                ctx_block["cache_control"] = {"type": "ephemeral"}
            blocks.append(ctx_block)

        return blocks

    def _format_tools(self, tools: list[dict]) -> str:
        """Format tool definitions as XML for caching."""
        parts = []
        for tool in tools:
            parts.append(
                f'<tool name="{tool.get("name", "")}">\n'
                f'  <description>{tool.get("description", "")}</description>\n'
                f'  <schema>{tool.get("input_schema", {})}</schema>\n'
                f"</tool>"
            )
        return "\n".join(parts)

    def estimate_cache_savings(self, input_tokens: int) -> float:
        """Estimate cost savings from prompt caching.

        Cache reads are 90% cheaper than base input tokens.
        """
        cache_read_price = 0.0003 / 1000  # $0.0003 per 1K cache read tokens
        base_price = 0.003 / 1000          # $0.003 per 1K input tokens
        return input_tokens * (base_price - cache_read_price)

    def record_hit(self, tokens_saved: int = 0) -> None:
        """Record a cache hit."""
        self._hits += 1
        self._savings_estimate += self.estimate_cache_savings(tokens_saved)

    def record_miss(self) -> None:
        """Record a cache miss."""
        self._misses += 1

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / max(total, 1)
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
            "estimated_savings_usd": round(self._savings_estimate, 4),
        }
