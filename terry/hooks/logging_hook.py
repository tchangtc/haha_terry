"""Logging hook - audit trail for tool usage."""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def log_hook(block) -> None:
    """PreToolUse hook: log every tool call."""
    args_preview = str(list(block.input.values())[:2])[:80]
    timestamp = datetime.now().strftime("%H:%M:%S")
    logger.debug("[%s] %s(%s)", timestamp, block.name, args_preview)
    return None
