"""Extended thinking and smart context window allocation.

Implements intelligent token budget distribution across system prompt,
tool definitions, conversation history, and output space.
"""

from __future__ import annotations


class ExtendedThinking:
    """Smart context window allocation for optimal LLM performance."""

    DEFAULT_ALLOCATION = {
        "system_prompt": 0.10,    # System prompt + tool definitions
        "active_context": 0.50,   # Recent messages + tool results
        "history": 0.25,          # Compressed conversation history
        "output": 0.15,           # Output token budget
    }

    MODEL_WINDOWS: dict[str, int] = {
        "claude-sonnet-4-20250514": 200_000,
        "claude-3-5-sonnet-20241022": 200_000,
        "claude-3-opus-20240229": 200_000,
        "claude-3-haiku-20240307": 200_000,
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "o1": 200_000,
        "gpt-4-turbo-preview": 128_000,
        "deepseek-chat": 64_000,
        "deepseek-reasoner": 64_000,
        "qwen-plus": 131_072,
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        allocation: dict[str, float] | None = None,
    ):
        self.model = model
        self.allocation = allocation or self.DEFAULT_ALLOCATION.copy()
        self.total = self._get_window(model)

    def _get_window(self, model: str) -> int:
        """Get the context window size for a model."""
        if model in self.MODEL_WINDOWS:
            return self.MODEL_WINDOWS[model]
        for prefix, window in sorted(
            self.MODEL_WINDOWS.items(), key=lambda x: -len(x[0])
        ):
            if model.startswith(prefix):
                return window
        return 1_000_000

    def allocate(self) -> dict[str, int]:
        """Calculate token budgets for each context zone.

        Returns:
            Dict with token budgets for each zone
        """
        budgets = {}
        for zone, ratio in self.allocation.items():
            budgets[zone] = int(self.total * ratio)
        return budgets

    def estimate_system_prompt_tokens(self, system: str, tools: list[dict]) -> int:
        """Estimate tokens used by system prompt and tool definitions."""
        from .context_compact import get_token_count
        tool_text = "\n".join(str(t) for t in (tools or []))
        return get_token_count(system + "\n" + tool_text, self.model)

    def estimate_history_tokens(self, messages: list[dict]) -> int:
        """Estimate tokens in conversation history."""
        from .context_compact import get_token_count
        text = "\n".join(str(m.get("content", "")) for m in messages)
        return get_token_count(text, self.model)

    def suggest_compression_threshold(self, messages: list[dict], system: str) -> float:
        """Suggest compression threshold based on current usage."""
        used = self.estimate_history_tokens(messages) + \
               self.estimate_system_prompt_tokens(system, [])
        ratio = used / max(self.total, 1)
        return min(ratio, 0.9)

    def can_fit(self, messages: list[dict], system: str, output_budget: int = 4000) -> bool:
        """Check if messages fit within the model's context window."""
        total = (
            self.estimate_system_prompt_tokens(system, []) +
            self.estimate_history_tokens(messages) +
            output_budget
        )
        return total < self.total * 0.95

    def optimize_allocation(self, messages: list[dict], system: str) -> dict[str, int]:
        """Dynamically adjust allocation based on actual content sizes."""
        budgets = self.allocate()
        sys_tokens = self.estimate_system_prompt_tokens(system, [])
        history_tokens = self.estimate_history_tokens(messages)

        # If system prompt is small, give more to history
        if sys_tokens < budgets["system_prompt"] * 0.5:
            surplus = budgets["system_prompt"] - sys_tokens
            budgets["history"] += surplus
            budgets["system_prompt"] = sys_tokens

        # If history is huge, take from output
        if history_tokens > budgets["history"]:
            deficit = history_tokens - budgets["history"]
            budgets["output"] = max(1000, budgets["output"] - deficit)

        return budgets
