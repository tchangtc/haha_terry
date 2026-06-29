"""Cost & token usage tracker — transparent, predictable, user-facing.

Claude Code users are in open revolt over unpredictable costs (+691 usage
limits, +722 cost spikes, +245 cache TTL regression). This module gives
users real-time visibility into what they're spending.

Usage:
    from terry.core.cost_tracker import CostTracker
    tracker = CostTracker()
    tracker.record_call("claude-sonnet-4-6", 500, 200)
    print(tracker.get_summary())
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

# Model pricing (USD per 1K tokens, approximate as of 2026-06)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {"input": 0.001, "output": 0.005},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-8": {"input": 0.015, "output": 0.075},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "deepseek-v3": {"input": 0.00027, "output": 0.0011},
}

DEFAULT_SESSION_BUDGET_USD = 5.0
BUDGET_WARNING_PCT = 80


@dataclass
class SessionCost:
    """Cost breakdown for a single session."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0


class CostTracker:
    """Real-time token and cost tracking with budget alerts."""

    def __init__(self, budget_usd: float = DEFAULT_SESSION_BUDGET_USD):
        self._budget = budget_usd
        self._models: dict[str, SessionCost] = defaultdict(
            lambda: SessionCost(model="")
        )
        self._start_time = time.time()
        self._warnings: list[str] = []
        self._total_cost = 0.0
        self._total_calls = 0

    def record_call(self, model: str, input_tokens: int, output_tokens: int):
        """Record an LLM API call with token counts."""
        pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.005})
        cost = (input_tokens / 1000) * pricing["input"] + \
               (output_tokens / 1000) * pricing["output"]

        mc = self._models[model]
        mc.model = model
        mc.input_tokens += input_tokens
        mc.output_tokens += output_tokens
        mc.calls += 1
        mc.cost_usd += cost

        self._total_cost += cost
        self._total_calls += 1

        # Budget warning
        if self._total_cost > self._budget * (BUDGET_WARNING_PCT / 100):
            if len(self._warnings) == 0:
                self._warnings.append(
                    f"Budget warning: ${self._total_cost:.2f} of "
                    f"${self._budget:.2f} used ({BUDGET_WARNING_PCT}%)"
                )

    def get_summary(self) -> dict:
        """Get a human-readable cost summary."""
        return {
            "session_duration": f"{time.time() - self._start_time:.0f}s",
            "total_cost": f"${self._total_cost:.4f}",
            "total_calls": self._total_calls,
            "budget": f"${self._budget:.2f}",
            "budget_remaining": f"${self._budget - self._total_cost:.2f}",
            "by_model": {
                m.model: {
                    "calls": m.calls,
                    "tokens_in": m.input_tokens,
                    "tokens_out": m.output_tokens,
                    "cost": f"${m.cost_usd:.4f}",
                }
                for m in self._models.values()
            },
            "warnings": self._warnings,
        }

    def get_total_tokens(self) -> dict[str, int]:
        """Get total token counts."""
        return {
            "input": sum(m.input_tokens for m in self._models.values()),
            "output": sum(m.output_tokens for m in self._models.values()),
        }

    def reset_budget(self, new_budget: float):
        """Reset the session budget."""
        self._budget = new_budget
        self._warnings.clear()
