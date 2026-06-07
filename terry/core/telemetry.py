"""OpenTelemetry observability — traces, metrics, structured events.

Provides:
  - Span-based tracing for Agent.run() and tool execution
  - Latency histograms for LLM calls and tool execution
  - Error rate counters
  - Structured event logging
  - OTLP export (optional, via environment variable OTEL_EXPORTER_OTLP_ENDPOINT)
  - Zero-dependency fallback when OTel SDK not installed
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from terry import __version__


class Span:
    """Minimal span implementation — OTel-compatible when SDK available."""

    def __init__(self, name: str, parent: Span | None = None):
        self.name = name
        self.parent = parent
        self.start_time = time.time()
        self.end_time: float | None = None
        self.attributes: dict[str, Any] = {}
        self.events: list[dict] = []
        self.status = "ok"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        self.events.append({"name": name, "timestamp": time.time(), "attributes": attributes or {}})

    def set_status(self, status: str) -> None:
        self.status = status

    def finish(self) -> None:
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000


class MetricsRegistry:
    """In-memory metrics store with optional OTLP export."""

    def __init__(self):
        self.counters: dict[str, int] = {}
        self.histograms: dict[str, list[float]] = {}
        self.gauges: dict[str, float] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def record_histogram(self, name: str, value: float) -> None:
        self.histograms.setdefault(name, []).append(value)

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def snapshot(self) -> dict:
        hist_snap = {}
        for name, values in self.histograms.items():
            if values:
                hist_snap[name] = {
                    "count": len(values),
                    "avg_ms": round(sum(values) / len(values), 1),
                    "p50_ms": round(sorted(values)[len(values)//2], 1),
                    "p95_ms": round(sorted(values)[int(len(values)*0.95)], 1) if len(values) >= 20 else None,
                }
        return {
            "counters": self.counters.copy(),
            "histograms": hist_snap,
            "gauges": self.gauges.copy(),
        }


class Telemetry:
    """Unified observability layer for Terry.

    Usage:
        tel = Telemetry()
        with tel.trace("agent.run") as span:
            span.set_attribute("user_message_length", 42)
            # ... agent work ...
            tel.metrics.increment("agent.runs")
            tel.metrics.record_histogram("agent.duration_ms", duration)
    """

    def __init__(self, service_name: str = "terry", otlp_endpoint: str | None = None):
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint
        self.metrics = MetricsRegistry()
        self._current_span: Span | None = None
        self._otel_available = False
        self._init_otel()

    def _init_otel(self) -> None:
        """Try to initialize OTel SDK. Gracefully degrades if not installed."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.semconv.resource import ResourceAttributes

            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: self.service_name,
                ResourceAttributes.SERVICE_VERSION: __version__,
            })
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)

            if self.otlp_endpoint:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))

            self._otel_available = True
        except ImportError:
            self._otel_available = False

    @contextmanager
    def trace(self, name: str, **attributes):
        """Context manager for span-based tracing.

        Usage:
            with tel.trace("agent.run", user_msg_len=42) as span:
                # ... work ...
                span.add_event("llm_call_started")
        """
        span = Span(name, self._current_span)
        for k, v in attributes.items():
            span.set_attribute(k, v)

        prev = self._current_span
        self._current_span = span

        try:
            if self._otel_available:
                from opentelemetry import trace
                tracer = trace.get_tracer(self.service_name)
                with tracer.start_as_current_span(name) as otel_span:
                    for k, v in attributes.items():
                        otel_span.set_attribute(k, v)
                    yield span
            else:
                yield span
        except Exception:
            yield span
        finally:
            span.finish()
            self._current_span = prev
            self.metrics.record_histogram(f"{name}.duration_ms", span.duration_ms)
            if span.status != "ok":
                self.metrics.increment(f"{name}.errors")

    def event(self, name: str, **data) -> None:
        """Log a structured event."""
        if self._current_span:
            self._current_span.add_event(name, data)

    def error(self, name: str, error: Exception, **data) -> None:
        """Log an error event."""
        self.metrics.increment(f"{name}.errors")
        if self._current_span:
            self._current_span.set_status("error")
            self._current_span.add_event("error", {"error": str(error), **data})

    def snapshot(self) -> dict:
        return {
            "service": self.service_name,
            "metrics": self.metrics.snapshot(),
            "active_span": self._current_span.name if self._current_span else None,
        }
