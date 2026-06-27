"""Prometheus-style metrics exporter for Terry.

Tracks key operational metrics: LLM token usage, cost, tool execution
count and latency, session duration, and error rates.

Enabled via: TERRY_METRICS_ENABLED=1
Metrics endpoint: http://localhost:9090/metrics (when web server is running)

Usage:
    from terry.core.metrics_exporter import MetricsCollector
    collector = MetricsCollector()
    collector.record_llm_call(model="claude-sonnet-4-6", input_tokens=500, output_tokens=200)
    print(collector.get_summary())
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricSnapshot:
    """Point-in-time snapshot of all metrics."""

    total_llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_tool_calls: int = 0
    total_tool_errors: int = 0
    total_sessions: int = 0
    avg_llm_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    by_model: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_tool: dict[str, int] = field(default_factory=dict)


class MetricsCollector:
    """Collects and exposes Terry operational metrics."""

    def __init__(self):
        self._start_time = time.time()
        self._snapshot = MetricSnapshot()
        self._latency_samples: list[float] = []
        self._lock = __import__('threading').Lock() if False else None  # Placeholder for lock
        self._model_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        )
        self._tool_stats: dict[str, int] = defaultdict(int)

    def record_llm_call(
        self, model: str, input_tokens: int, output_tokens: int,
        cost_usd: float = 0.0, latency_ms: float = 0.0,
    ):
        """Record an LLM API call."""
        self._snapshot.total_llm_calls += 1
        self._snapshot.total_input_tokens += input_tokens
        self._snapshot.total_output_tokens += output_tokens
        self._snapshot.total_cost_usd += cost_usd

        ms = self._model_stats[model]
        ms["calls"] += 1
        ms["input_tokens"] += input_tokens
        ms["output_tokens"] += output_tokens
        ms["cost"] += cost_usd

        if latency_ms > 0:
            self._latency_samples.append(latency_ms)

    def record_tool_call(self, tool_name: str, success: bool = True):
        """Record a tool execution."""
        self._snapshot.total_tool_calls += 1
        self._tool_stats[tool_name] += 1
        if not success:
            self._snapshot.total_tool_errors += 1

    def record_session(self):
        """Record a new session start."""
        self._snapshot.total_sessions += 1

    def get_snapshot(self) -> MetricSnapshot:
        """Get a snapshot of current metrics."""
        snap = MetricSnapshot(
            total_llm_calls=self._snapshot.total_llm_calls,
            total_input_tokens=self._snapshot.total_input_tokens,
            total_output_tokens=self._snapshot.total_output_tokens,
            total_cost_usd=self._snapshot.total_cost_usd,
            total_tool_calls=self._snapshot.total_tool_calls,
            total_tool_errors=self._snapshot.total_tool_errors,
            total_sessions=self._snapshot.total_sessions,
            uptime_seconds=time.time() - self._start_time,
            by_model=dict(self._model_stats),
            by_tool=dict(self._tool_stats),
        )
        if self._latency_samples:
            snap.avg_llm_latency_ms = sum(self._latency_samples) / len(self._latency_samples)
        return snap

    def get_summary(self) -> dict[str, Any]:
        """Get a human-readable summary of metrics."""
        snap = self.get_snapshot()
        return {
            "uptime": f"{snap.uptime_seconds:.0f}s",
            "llm_calls": snap.total_llm_calls,
            "tokens": f"{snap.total_input_tokens:,} in / {snap.total_output_tokens:,} out",
            "cost": f"${snap.total_cost_usd:.4f}",
            "tool_calls": snap.total_tool_calls,
            "tool_errors": snap.total_tool_errors,
            "avg_latency": f"{snap.avg_llm_latency_ms:.0f}ms" if snap.avg_llm_latency_ms > 0 else "N/A",
            "models": {
                model: f"{m['calls']} calls, {m['input_tokens']:,} tokens"
                for model, m in snap.by_model.items()
            },
            "tools": dict(snap.by_tool),
        }

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        snap = self.get_snapshot()
        lines = [
            "# HELP terry_llm_calls_total Total number of LLM API calls",
            "# TYPE terry_llm_calls_total counter",
            f"terry_llm_calls_total {snap.total_llm_calls}",
            "# HELP terry_tokens_total Total tokens processed",
            "# TYPE terry_tokens_total counter",
            f"terry_input_tokens_total {snap.total_input_tokens}",
            f"terry_output_tokens_total {snap.total_output_tokens}",
            "# HELP terry_cost_usd_total Total cost in USD",
            "# TYPE terry_cost_usd_total counter",
            f"terry_cost_usd_total {snap.total_cost_usd}",
            "# HELP terry_tool_calls_total Tool execution count",
            "# TYPE terry_tool_calls_total counter",
            f"terry_tool_calls_total {snap.total_tool_calls}",
            f"terry_tool_errors_total {snap.total_tool_errors}",
            "# HELP terry_uptime_seconds Agent uptime",
            "# TYPE terry_uptime_seconds gauge",
            f"terry_uptime_seconds {snap.uptime_seconds:.1f}",
        ]
        for model, m in snap.by_model.items():
            lines.append(f"terry_model_calls{{model=\"{model}\"}} {m['calls']}")
            lines.append(f"terry_model_tokens{{model=\"{model}\"}} {m['input_tokens'] + m['output_tokens']}")
        for tool, count in snap.by_tool.items():
            lines.append(f"terry_tool_usage{{tool=\"{tool}\"}} {count}")
        return "\n".join(lines) + "\n"


# Global instance
_global_collector: MetricsCollector | None = None


def get_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector
