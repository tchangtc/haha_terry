"""Metrics collection - track usage, performance, and costs."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir


class Metrics:
    """Collects and stores usage metrics."""

    def __init__(self, metrics_dir: Path | None = None):
        """Initialize metrics collector.

        Args:
            metrics_dir: Directory to store metrics files
        """
        self.metrics_dir = metrics_dir or get_terry_dir("metrics")
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

        # In-memory counters
        self.counters: dict[str, int] = {}
        self.timers: dict[str, list[float]] = {}
        self.costs: dict[str, float] = {}

        # Session start time
        self.session_start = datetime.now()

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter.

        Args:
            name: Counter name
            value: Value to add
        """
        self.counters[name] = self.counters.get(name, 0) + value

    def timer_start(self) -> float:
        """Start a timer.

        Returns:
            Start timestamp
        """
        return time.time()

    def timer_stop(self, name: str, start_time: float) -> float:
        """Stop a timer and record duration.

        Args:
            name: Timer name
            start_time: Start timestamp from timer_start()

        Returns:
            Duration in seconds
        """
        duration = time.time() - start_time

        if name not in self.timers:
            self.timers[name] = []
        self.timers[name].append(duration)

        return duration

    def add_cost(self, provider: str, cost: float) -> None:
        """Add cost for a provider.

        Args:
            provider: Provider name (e.g., 'anthropic', 'openai')
            cost: Cost in USD
        """
        self.costs[provider] = self.costs.get(provider, 0.0) + cost

    def get_counter(self, name: str) -> int:
        """Get counter value.

        Args:
            name: Counter name

        Returns:
            Counter value
        """
        return self.counters.get(name, 0)

    def get_timer_stats(self, name: str) -> dict[str, float]:
        """Get timer statistics.

        Args:
            name: Timer name

        Returns:
            Dictionary with min, max, avg, count
        """
        if name not in self.timers or not self.timers[name]:
            return {"min": 0, "max": 0, "avg": 0, "count": 0}

        times = self.timers[name]
        return {
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / len(times),
            "count": len(times),
            "total": sum(times),
        }

    def get_total_cost(self) -> float:
        """Get total cost across all providers.

        Returns:
            Total cost in USD
        """
        return sum(self.costs.values())

    def get_summary(self) -> dict[str, Any]:
        """Get complete metrics summary.

        Returns:
            Dictionary with all metrics
        """
        session_duration = (datetime.now() - self.session_start).total_seconds()

        return {
            "session_start": self.session_start.isoformat(),
            "session_duration": session_duration,
            "counters": self.counters.copy(),
            "timers": {
                name: self.get_timer_stats(name)
                for name in self.timers
            },
            "costs": self.costs.copy(),
            "total_cost": self.get_total_cost(),
        }

    def save(self, filename: str | None = None) -> Path:
        """Save metrics to disk.

        Args:
            filename: Optional custom filename

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.json"

        metrics_file = self.metrics_dir / filename
        summary = self.get_summary()

        metrics_file.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return metrics_file

    def load(self, filename: str) -> bool:
        """Load metrics from disk.

        Args:
            filename: Metrics filename

        Returns:
            True if loaded successfully
        """
        metrics_file = self.metrics_dir / filename

        if not metrics_file.exists():
            return False

        try:
            data = json.loads(metrics_file.read_text(encoding="utf-8"))

            self.session_start = datetime.fromisoformat(data.get("session_start", datetime.now().isoformat()))
            self.counters = data.get("counters", {})
            self.costs = data.get("costs", {})

            # Reconstruct timers from stats
            self.timers = {}
            for name, stats in data.get("timers", {}).items():
                # We can only restore average, not individual measurements
                count = stats.get("count", 0)
                avg = stats.get("avg", 0)
                if count > 0:
                    self.timers[name] = [avg] * count

            return True
        except Exception:
            return False

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters = {}
        self.timers = {}
        self.costs = {}
        self.session_start = datetime.now()


# Cost estimation models (USD per 1K tokens)
# Prices as of 2026-06. Always verify with provider's latest pricing page.
COST_MODELS = {
    # Anthropic Claude models
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    # OpenAI models
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "o1": {"input": 0.015, "output": 0.06},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    # DeepSeek models
    "deepseek-chat": {"input": 0.00027, "output": 0.0011},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
}

# Fallback: use fuzzy matching for unknown model IDs
_MODEL_COST_FALLBACK = {
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "claude-haiku-4": {"input": 0.0008, "output": 0.004},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for a model call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    # Exact match first
    if model in COST_MODELS:
        rates = COST_MODELS[model]
    else:
        # Fuzzy match by prefix
        matched = None
        for prefix, rates in _MODEL_COST_FALLBACK.items():
            if model.startswith(prefix):
                matched = rates
                break
        if matched is None:
            return 0.0
        rates = matched

    input_cost = (input_tokens / 1000) * rates["input"]
    output_cost = (output_tokens / 1000) * rates["output"]

    return input_cost + output_cost


# Global metrics instance
_metrics_instance: Metrics | None = None


def get_metrics(metrics_dir: Path | None = None) -> Metrics:
    """Get or create the global metrics instance.

    Args:
        metrics_dir: Optional metrics directory override

    Returns:
        Metrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = Metrics(metrics_dir)
    return _metrics_instance


def set_metrics(instance: Metrics) -> None:
    """Inject a custom Metrics instance (for testing/DI)."""
    global _metrics_instance
    _metrics_instance = instance


def reset_metrics() -> None:
    """Reset metrics singleton (forces re-initialization on next get)."""
    global _metrics_instance
    _metrics_instance = None
