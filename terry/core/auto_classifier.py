"""Heuristic auto-mode classifier for smart permission decisions.

Scoring-based classifier that determines whether a tool operation should
be auto-approved in auto mode. No ML dependency — pure heuristic scoring
based on tool risk weights, command danger patterns, path safety, and
session approval memory.
"""

from __future__ import annotations

import logging
from enum import IntEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TrustLevel(IntEnum):
    """Trust level for auto-mode decisions."""
    HIGH_TRUST = 2
    LOW_TRUST = 1
    NO_TRUST = 0


_TOOL_WEIGHTS: dict[str, float] = {
    "read_file": 0.90, "read_image": 0.90, "ls": 0.95, "ls_tool": 0.95,
    "glob": 0.90, "grep": 0.90, "find_tool": 0.90,
    "web_search": 0.80, "web_fetch": 0.70, "bash": 0.30,
    "write_file": 0.50, "edit_file": 0.50, "multi_edit": 0.40,
    "notebook": 0.60, "todo_write": 0.85, "notes": 0.85,
    "calculator": 0.95, "weather": 0.90, "timer": 0.85, "reminder": 0.85,
}

_DANGER_PATTERNS = [
    "rm ", "dd ", "chmod ", "chown ", "mkfs", " > ", " | ", "sudo ", "su ",
    "shutdown", "reboot", "halt", "docker rm", "docker system prune",
    "git push --force", "git reset --hard", "pip uninstall", "npm uninstall",
    "DROP TABLE", "DROP DATABASE", "TRUNCATE",
]


class AutoModeClassifier:
    """Heuristic classifier for auto-mode permission decisions."""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self._approved: set[str] = set()
        self._decision_count = 0

    def get_trust_level(self, tool_name: str, args: dict[str, Any], workdir: Path) -> TrustLevel:
        score = self._score(tool_name, args, workdir)
        self._decision_count += 1
        if score >= self.threshold: return TrustLevel.HIGH_TRUST
        elif score >= self.threshold * 0.4: return TrustLevel.LOW_TRUST
        else: return TrustLevel.NO_TRUST

    def record_approval(self, tool_name: str, command_or_path: str) -> None:
        self._approved.add(f"{tool_name}:{command_or_path}")

    def _score(self, tool_name: str, args: dict[str, Any], workdir: Path) -> float:
        score = _TOOL_WEIGHTS.get(tool_name, 0.5)
        if tool_name == "bash":
            command = args.get("command", "")
            for pattern in _DANGER_PATTERNS:
                if pattern in command: score -= 0.2
            if len(command) > 200: score -= 0.1
        if tool_name in ("read_file", "write_file", "edit_file", "multi_edit"):
            path_str = args.get("path", args.get("file_path", ""))
            if path_str:
                try:
                    resolved = (workdir / path_str).resolve()
                    if resolved.is_relative_to(workdir.resolve()): score += 0.15
                    else: score -= 0.3
                except (ValueError, OSError): score -= 0.1
        ident = self._make_identifier(tool_name, args)
        if ident in self._approved: score += 0.2
        return max(0.0, min(1.0, score))

    def get_decision_count(self) -> int:
        """Return total number of classification decisions made."""
        return self._decision_count

    @staticmethod
    def _make_identifier(tool_name: str, args: dict[str, Any]) -> str:
        if tool_name == "bash":
            cmd = args.get("command", "")
            return f"bash:{cmd[:80]}"
        elif tool_name in ("read_file", "write_file", "edit_file", "multi_edit"):
            p = args.get("path", args.get("file_path", ""))
            return f"{tool_name}:{p}"
        return f"{tool_name}:{str(args)[:80]}"
