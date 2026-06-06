"""Hook system - event-based extension points."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class HookRegistry:
    """Registry for event hooks."""

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {
            "UserPromptSubmit": [],
            "PreToolUse": [],
            "PostToolUse": [],
            "Stop": [],
        }

    def register(self, event: str, callback: Callable):
        """Register a callback for an event."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def trigger(self, event: str, *args, **kwargs) -> Any:
        """Trigger all callbacks for an event.

        Returns the first non-None result (used for blocking operations like permission checks).
        """
        for callback in self._hooks.get(event, []):
            result = callback(*args, **kwargs)
            if result is not None:
                return result
        return None


# Global hook registry
hook_registry = HookRegistry()
