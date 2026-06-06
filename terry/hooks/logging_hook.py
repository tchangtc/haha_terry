"""Logging hook - audit trail for tool usage."""

from __future__ import annotations

from datetime import datetime


def log_hook(block) -> None:
    """PreToolUse hook: log every tool call."""
    args_preview = str(list(block.input.values())[:2])[:80]
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\033[90m[{timestamp}] {block.name}({args_preview})\033[0m")
    return None
