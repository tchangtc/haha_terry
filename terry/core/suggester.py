"""Proactive suggestion mode - agent suggests next actions based on context.

Analyzes conversation and tool output patterns to proactively suggest
helpful next steps to the user.
"""

from __future__ import annotations

import re
from typing import Any


class ProactiveSuggester:
    """Analyzes agent context and suggests next actions.

    Detects patterns like errors that were just fixed, completed
    refactors that need review, or new features that need tests.
    """

    # Pattern → suggestion mapping
    SUGGESTION_PATTERNS: list[tuple[str, str, int]] = [
        # (trigger_pattern, suggestion, priority: 1=high, 3=low)
        (r"Error.*fixed|issue.*resolved|bug.*fixed", "Run tests to verify the fix", 1),
        (r"def test_|test_.*\.py", "Run the new tests with pytest", 1),
        (r"new file.*created|file written.*\.py", "Add a test for the new code", 2),
        (r"import.*added|dependency.*installed", "Update requirements.txt or pyproject.toml", 2),
        (r"refactor.*complete|restructure.*done", "Review the changes with /plan review", 2),
        (r"config.*updated|setting.*changed", "Check if documentation needs updating", 3),
        (r"deprecated|warning.*deprecated", "Consider migrating away from deprecated API", 2),
        (r"TODO|FIXME|HACK", "Address the remaining TODOs", 2),
        (r"performance|slow|optimize", "Profile the code to verify improvement", 2),
        (r"security|vulnerability", "Run a security scan with semgrep or bandit", 1),
    ]

    def __init__(self, max_suggestions: int = 3):
        self.max_suggestions = max_suggestions

    def analyze(
        self, messages: list[dict], tool_outputs: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Analyze context and generate suggestions.

        Returns list of suggestion dicts with 'text' and 'priority'.
        """
        suggestions = []
        context_text = " ".join(
            str(m.get("content", "")) for m in messages[-10:]
        )
        if tool_outputs:
            context_text += " " + " ".join(tool_outputs[-5:])

        context_lower = context_text.lower()

        for pattern, suggestion, priority in self.SUGGESTION_PATTERNS:
            if re.search(pattern, context_lower):
                # Avoid duplicate suggestions
                if not any(s["text"] == suggestion for s in suggestions):
                    suggestions.append({
                        "text": suggestion,
                        "priority": priority,
                        "trigger": pattern,
                    })

        # Sort by priority (1 = most important)
        suggestions.sort(key=lambda s: s["priority"])
        return suggestions[:self.max_suggestions]

    def format_suggestions(self, suggestions: list[dict]) -> str:
        """Format suggestions for display."""
        if not suggestions:
            return ""

        lines = ["\n💡 **Suggestions:**"]
        for s in suggestions:
            priority_icon = {1: "🔴", 2: "🟡", 3: "🟢"}.get(s["priority"], "⚪")
            lines.append(f"  {priority_icon} {s['text']}")
        return "\n".join(lines)

    def should_suggest(self, messages: list[dict]) -> bool:
        """Determine if it's a good time to make suggestions.

        Suggests when the agent has just completed a task
        (not during active tool execution).
        """
        if len(messages) < 3:
            return False

        # Check if the last assistant message looks like a completion
        last_msgs = [m for m in messages[-5:] if m.get("role") == "assistant"]
        if not last_msgs:
            return False

        last_content = str(last_msgs[-1].get("content", "")).lower()
        completion_markers = [
            "done", "completed", "finished", "created", "updated",
            "fixed", "resolved", "ready", "success",
        ]
        return any(marker in last_content for marker in completion_markers)
