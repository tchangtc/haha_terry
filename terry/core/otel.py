"""OpenTelemetry integration for Terry.

Provides automatic tracing of LLM calls, tool executions, and agent
orchestration. Supports OTLP exporter (Jaeger, Grafana, etc.) and
console output for development.

Enabled via: TERRY_OTEL_ENABLED=1
OTLP endpoint: TERRY_OTEL_ENDPOINT (default: http://localhost:4317)

Usage:
    from terry.core.otel import setup_otel, trace_llm_call, trace_tool

    setup_otel()
    with trace_llm_call("claude-sonnet-4-6", 500) as span:
        response = llm.chat(messages)

Design: zero overhead when disabled — all tracing functions are no-ops
unless setup_otel() has been called.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_otel_enabled = os.environ.get("TERRY_OTEL_ENABLED", "").lower() in ("1", "true", "yes")
_tracer = None
_setup_done = False


def setup_otel(
    service_name: str = "terry",
    endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> bool:
    """Initialize OpenTelemetry with OTLP exporter.

    Returns True if setup succeeded, False if otel is not available.
    """
    global _otel_enabled, _tracer, _setup_done

    if _setup_done:
        return _otel_enabled

    _setup_done = True

    if not _otel_enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})

        provider = TracerProvider(resource=resource)

        # Try OTLP exporter first
        otlp_endpoint = endpoint or os.environ.get(
            "TERRY_OTEL_ENDPOINT", "http://localhost:4317"
        )
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTel: OTLP exporter configured at %s", otlp_endpoint)
        except ImportError:
            # Fallback to console
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("OTel: console exporter (install opentelemetry-exporter-otlp for OTLP)")

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)
        _otel_enabled = True
        logger.info("OTel initialized for service '%s'", service_name)
        return True
    except ImportError:
        logger.debug("OpenTelemetry SDK not installed — tracing disabled")
        _otel_enabled = False
        return False


@contextmanager
def trace_llm_call(model: str, input_tokens: int = 0):
    """Trace an LLM API call. No-op if otel is disabled."""
    if not _otel_enabled or _tracer is None:
        yield None
        return

    t0 = time.time()
    span = _tracer.start_span(
        "llm.chat",
        attributes={
            "llm.model": model,
            "llm.input_tokens": input_tokens,
        },
    )
    try:
        yield span
    except Exception:
        span.set_attribute("error", True)
        raise
    finally:
        span.set_attribute("llm.duration_ms", (time.time() - t0) * 1000)
        span.end()


@contextmanager
def trace_tool(name: str, input_summary: str = ""):
    """Trace a tool execution. No-op if otel is disabled."""
    if not _otel_enabled or _tracer is None:
        yield None
        return

    t0 = time.time()
    span = _tracer.start_span(
        f"tool.{name}",
        attributes={
            "tool.name": name,
            "tool.input_summary": input_summary[:200],
        },
    )
    try:
        yield span
    except Exception:
        span.set_attribute("error", True)
        raise
    finally:
        span.set_attribute("tool.duration_ms", (time.time() - t0) * 1000)
        span.end()


@contextmanager
def trace_agent(agent_id: str, task: str = ""):
    """Trace an agent orchestration span. No-op if otel is disabled."""
    if not _otel_enabled or _tracer is None:
        yield None
        return

    t0 = time.time()
    span = _tracer.start_span(
        "agent.execute",
        attributes={
            "agent.id": agent_id,
            "agent.task": task[:200],
        },
    )
    try:
        yield span
    except Exception:
        span.set_attribute("error", True)
        raise
    finally:
        span.set_attribute("agent.duration_ms", (time.time() - t0) * 1000)
        span.end()


def otel_available() -> bool:
    """Check if OpenTelemetry is available and enabled."""
    return _otel_enabled and _tracer is not None
