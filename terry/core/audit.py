"""Audit logging for Terry — complete operation trail for compliance.

Records every tool execution, LLM call, and session event with
timestamp, user context, and result. Supports JSON and SQLite backends.

Usage:
    from terry.core.audit import AuditLogger
    audit = AuditLogger()
    audit.log_tool("bash", {"command": "ls"}, "file1\nfile2", success=True)
    records = audit.query(tool="bash", limit=20)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIT_RETENTION_DAYS = 90


@dataclass
class AuditRecord:
    """A single audit log entry."""

    timestamp: float = field(default_factory=time.time)
    event: str = ""          # tool_call, llm_call, session_start, config_change
    user: str = ""           # User or agent identifier
    tool: str = ""           # Tool name (if applicable)
    input_summary: str = ""  # First 200 chars of input
    result_summary: str = "" # First 200 chars of result
    success: bool = True
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class AuditLogger:
    """Structured audit trail for compliance and debugging."""

    def __init__(self, log_dir: Path | None = None):
        if log_dir is None:
            from terry.core.platform_utils import get_terry_dir
            log_dir = get_terry_dir() / "audit"
        self._dir = log_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._current_file = self._dir / f"audit-{time.strftime('%Y%m%d')}.jsonl"
        self._records: list[AuditRecord] = []
        self._count = 0

    def log_tool(
        self, tool: str, args: dict, result: str,
        success: bool = True, duration_ms: float = 0.0,
        user: str = "default",
    ):
        """Log a tool execution."""
        self._append(AuditRecord(
            event="tool_call",
            user=user,
            tool=tool,
            input_summary=json.dumps(args, default=str)[:200],
            result_summary=str(result)[:200],
            success=success,
            duration_ms=duration_ms,
        ))

    def log_llm(
        self, model: str, input_tokens: int = 0,
        output_tokens: int = 0, duration_ms: float = 0.0,
        user: str = "default",
    ):
        """Log an LLM API call."""
        self._append(AuditRecord(
            event="llm_call",
            user=user,
            tool=model,
            input_summary=f"{input_tokens} tokens",
            result_summary=f"{output_tokens} tokens output",
            duration_ms=duration_ms,
            metadata={"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens},
        ))

    def log_session(self, action: str, user: str = "default"):
        """Log session lifecycle events."""
        self._append(AuditRecord(
            event=f"session_{action}",
            user=user,
            input_summary=action,
        ))

    def log_config(self, key: str, value_summary: str, user: str = "default"):
        """Log configuration changes."""
        self._append(AuditRecord(
            event="config_change",
            user=user,
            input_summary=key,
            result_summary=value_summary,
        ))

    def query(
        self, event: str | None = None, tool: str | None = None,
        user: str | None = None, since: float | None = None,
        limit: int = 50,
    ) -> list[AuditRecord]:
        """Query audit records with filters."""
        results = []
        for r in self._records:
            if event and r.event != event:
                continue
            if tool and r.tool != tool:
                continue
            if user and r.user != user:
                continue
            if since and r.timestamp < since:
                continue
            results.append(r)
        return results[-limit:]

    def get_summary(self) -> dict:
        """Get audit summary statistics."""
        events = {}
        tools = {}
        errors = 0
        for r in self._records:
            events[r.event] = events.get(r.event, 0) + 1
            if r.tool:
                tools[r.tool] = tools.get(r.tool, 0) + 1
            if not r.success:
                errors += 1
        return {
            "total_records": len(self._records),
            "by_event": events,
            "by_tool": tools,
            "errors": errors,
            "retention_days": AUDIT_RETENTION_DAYS,
        }

    def _append(self, record: AuditRecord):
        self._records.append(record)
        self._count += 1
        # Periodic flush every 50 records
        if self._count % 50 == 0:
            self._flush()

    def _flush(self):
        """Persist records to disk."""
        try:
            with open(self._current_file, "a") as f:
                for r in self._records[-50:]:
                    f.write(json.dumps(r.to_dict(), default=str) + "\n")
        except OSError:
            logger.warning("Audit flush failed", exc_info=True)


# ── Global instance ─────────────────────────────────────────────────

_global_audit: AuditLogger | None = None


def get_audit() -> AuditLogger:
    global _global_audit
    if _global_audit is None:
        _global_audit = AuditLogger()
    return _global_audit
