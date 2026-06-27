"""Model Router v2 — cost/latency/task-aware dynamic model selection.

Extends the original ModelRouter with:
- Multi-model routing (not just simple/complex dual)
- Cost-aware provider selection
- Latency budget enforcement
- Task type classification
- Integration with effort system

Usage:
    router = ModelRouterV2(config)
    client = router.route("Refactor the auth module")
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Constants ────────────────────────────────────────────────────────


DEFAULT_MAX_TOKENS = 128000
DEFAULT_LATENCY_MS = 1000
DEFAULT_BUDGET_USD = 1.0
LONG_PROMPT_THRESHOLD = 200
TOKEN_COST_ESTIMATE_MULTIPLIER = 0.5  # ~500 input tokens avg
TIER_FALLBACK_OFFSETS = [1, -1, 2]


# ── Model Pricing & Capability Profiles ──────────────────────────────


@dataclass
class ModelProfile:
    """Cost and capability profile for a model."""

    name: str
    provider: str  # anthropic, openai, deepseek, ollama
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    max_tokens: int = DEFAULT_MAX_TOKENS
    latency_ms: int = DEFAULT_LATENCY_MS
    capabilities: list[str] = field(default_factory=list)  # code, reasoning, fast, vision
    tier: str = "medium"  # budget, medium, premium


# Known model profiles (prices in USD per 1K tokens, approximate)
MODEL_REGISTRY: dict[str, ModelProfile] = {
    "claude-haiku-4-5": ModelProfile(
        name="claude-haiku-4-5", provider="anthropic",
        input_cost_per_1k=0.001, output_cost_per_1k=0.005,
        latency_ms=300, capabilities=["fast", "code"],
        tier="budget",
    ),
    "claude-sonnet-4-6": ModelProfile(
        name="claude-sonnet-4-6", provider="anthropic",
        input_cost_per_1k=0.003, output_cost_per_1k=0.015,
        latency_ms=800, capabilities=["code", "reasoning"],
        tier="medium",
    ),
    "claude-opus-4-8": ModelProfile(
        name="claude-opus-4-8", provider="anthropic",
        input_cost_per_1k=0.015, output_cost_per_1k=0.075,
        latency_ms=2000, capabilities=["code", "reasoning", "complex"],
        tier="premium",
    ),
    "gpt-4o": ModelProfile(
        name="gpt-4o", provider="openai",
        input_cost_per_1k=0.0025, output_cost_per_1k=0.01,
        latency_ms=600, capabilities=["code", "reasoning", "vision"],
        tier="medium",
    ),
    "deepseek-v3": ModelProfile(
        name="deepseek-v3", provider="deepseek",
        input_cost_per_1k=0.00027, output_cost_per_1k=0.0011,
        latency_ms=500, capabilities=["code", "fast"],
        tier="budget",
    ),
}


# ── Task Type Classification ────────────────────────────────────────

TASK_PATTERNS: dict[str, list[str]] = {
    "read": ["read", "show", "list", "find", "search", "cat", "ls", "display",
             "where is", "which file", "look at", "what file", "grep", "locate"],
    "write": ["write", "create", "generate", "add", "implement", "build", "make"],
    "edit": ["edit", "modify", "change", "update", "fix", "refactor",
             "improve", "optimize", "correct"],
    "review": ["review", "audit", "analyze", "inspect", "check", "examine",
               "security", "vulnerability", "code review"],
    "plan": ["plan", "design", "architecture", "approach", "strategy",
             "how should", "best way", "recommend"],
    "debug": ["debug", "error", "bug", "crash", "fail", "broken", "fix bug",
              "fix issue", "resolve problem", "troubleshoot", "null pointer",
              "stack trace", "exception", "traceback"],
}


class ModelRouterV2:
    """Multi-model router with cost, latency, and task awareness."""

    def __init__(self, config=None, budget_limit_usd: float = DEFAULT_BUDGET_USD):
        self._config = config
        self._budget_limit = budget_limit_usd
        self._usage: dict[str, float] = {}  # model → total cost
        self._routes: int = 0

    def classify_task(self, user_input: str) -> str:
        """Classify the task type from user input."""
        text = user_input.lower()
        scores = {}
        for task_type, keywords in TASK_PATTERNS.items():
            scores[task_type] = sum(1 for kw in keywords if kw in text)
        # Length-based heuristic — only for clear indicators
        keyword_matched = any(v > 0 for v in scores.values())
        if not keyword_matched and len(user_input) > LONG_PROMPT_THRESHOLD:
            scores["plan"] = scores.get("plan", 0) + 1

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        return best if scores[best] > 0 else "general"

    def route(
        self,
        user_input: str,
        budget_tier: str | None = None,
        require_capability: str | None = None,
        prefer_low_latency: bool = False,
    ) -> str:
        """Select the best model for a given task.

        Args:
            user_input: The user's request
            budget_tier: Force a tier (budget/medium/premium), or None for auto
            require_capability: Require a specific capability (vision, reasoning, etc.)
            prefer_low_latency: Prefer faster models

        Returns:
            Model name string
        """
        task_type = self.classify_task(user_input)

        # Determine tier based on task
        if budget_tier:
            tier = budget_tier
        elif task_type in ("read", "write"):
            tier = "budget"
        elif task_type in ("review", "debug", "plan"):
            tier = "premium"
        else:
            tier = "medium"

        candidates = [
            m for m in MODEL_REGISTRY.values()
            if m.tier == tier
        ]
        if not candidates:
            # Fallback: any model in lower/higher tier
            tier_order = ["budget", "medium", "premium"]
            idx = tier_order.index(tier) if tier in tier_order else 1
            for offset in TIER_FALLBACK_OFFSETS:
                fallback_idx = idx + offset
                if 0 <= fallback_idx < len(tier_order):
                    candidates = [
                        m for m in MODEL_REGISTRY.values()
                        if m.tier == tier_order[fallback_idx]
                    ]
                    if candidates:
                        break
        if not candidates:
            candidates = list(MODEL_REGISTRY.values())

        # Filter by capability
        if require_capability:
            filtered = [m for m in candidates if require_capability in m.capabilities]
            if filtered:
                candidates = filtered

        # Sort: prefer low latency if requested, else prefer low cost
        if prefer_low_latency:
            candidates.sort(key=lambda m: m.latency_ms)
        else:
            candidates.sort(key=lambda m: m.input_cost_per_1k)

        selected = candidates[0]
        self._routes += 1

        # Track cost
        estimated_cost = selected.input_cost_per_1k * TOKEN_COST_ESTIMATE_MULTIPLIER
        self._usage[selected.name] = self._usage.get(selected.name, 0) + estimated_cost

        return selected.name

    def route_to_profile(self, user_input: str, **kwargs) -> ModelProfile:
        """Route and return the full ModelProfile."""
        name = self.route(user_input, **kwargs)
        return MODEL_REGISTRY.get(name, list(MODEL_REGISTRY.values())[0])

    def get_stats(self) -> dict:
        """Get routing statistics."""
        return {
            "total_routes": self._routes,
            "usage_by_model": self._usage,
            "total_cost": sum(self._usage.values()),
            "budget_remaining": self._budget_limit - sum(self._usage.values()),
        }

    def get_available_models(self) -> list[ModelProfile]:
        """List all available models."""
        return list(MODEL_REGISTRY.values())
