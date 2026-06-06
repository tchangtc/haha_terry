"""Speculative execution engine - pre-fetch likely-needed resources.

When the agent makes a tool call that suggests it will need certain
files or search results next, the spec exec engine can start those
reads in parallel to reduce wall-clock latency.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any


class SpeculativeExecutor:
    """Pre-fetches resources the agent is likely to need next.

    Analyzes tool calls and conversation context to predict which
    files, symbols, or searches will be needed, then starts them
    in background threads before the next LLM call.
    """

    # Patterns that suggest the agent will need to read a file
    FILE_MENTION_PATTERN = re.compile(
        r"(?:read|open|check|look at|examine|inspect)\s+(?:the\s+)?(?:file\s+)?['\"]?([^\s'\"]+\.(?:py|js|ts|md|yaml|json|toml|txt))",
        re.IGNORECASE,
    )

    # Tools that suggest file access will follow
    TRIGGER_TOOLS = {"grep", "find", "ls", "glob", "git_diff", "git_status"}

    def __init__(self, max_prefetch: int = 5):
        self.max_prefetch = max_prefetch
        self._pending: dict[str, threading.Thread] = {}
        self._results: dict[str, str] = {}
        self._hits = 0
        self._misses = 0

    def analyze_tool_call(
        self, tool_name: str, tool_input: dict, tool_output: str
    ) -> list[str]:
        """Analyze a tool call and predict which files will be needed.

        Returns list of predicted file paths.
        """
        predictions = []

        if tool_name in self.TRIGGER_TOOLS:
            # Extract file paths from command output
            for line in tool_output.split("\n"):
                line = line.strip()
                if line.endswith((".py", ".js", ".ts", ".md", ".yaml", ".json")):
                    predictions.append(line.split()[-1] if " " in line else line)

        # Check for file mentions in bash commands
        if tool_name == "bash":
            command = tool_input.get("command", "")
            mentions = self.FILE_MENTION_PATTERN.findall(command)
            predictions.extend(mentions)

        return predictions[:self.max_prefetch]

    def prefetch_files(
        self, workdir: Path, filenames: list[str]
    ) -> None:
        """Start prefetching files in background threads.

        Args:
            workdir: Working directory
            filenames: File paths to prefetch
        """
        for filename in filenames:
            if filename in self._pending or filename in self._results:
                continue

            file_path = workdir / filename
            if not file_path.exists():
                continue

            def _read_and_store(fp: Path, name: str) -> None:
                try:
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    self._results[name] = content[:50_000]
                except Exception:
                    self._results[name] = f"Error reading {name}"

            thread = threading.Thread(
                target=_read_and_store,
                args=(file_path, filename),
                daemon=True,
            )
            self._pending[filename] = thread
            thread.start()

    def get_prefetched(self, filename: str) -> str | None:
        """Get prefetched content if available.

        Returns content or None if not prefetched.
        """
        result = self._results.pop(filename, None)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def clear(self) -> None:
        """Clear all prefetch state."""
        self._pending.clear()
        self._results.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get prefetch statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / max(total, 1):.1%}",
        }
