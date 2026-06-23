"""Hook system - event-based extension points with priority and async support."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HookEvent(StrEnum):
    """Typed hook events — prevents typo bugs, enables IDE autocomplete."""
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"
    BEFORE_GIT_COMMIT = "BeforeGitCommit"


# Backward-compatible string aliases for existing callers
_HOOK_ALIASES = {
    "UserPromptSubmit": HookEvent.USER_PROMPT_SUBMIT,
    "PreToolUse": HookEvent.PRE_TOOL_USE,
    "PostToolUse": HookEvent.POST_TOOL_USE,
    "Stop": HookEvent.STOP,
    "BeforeGitCommit": HookEvent.BEFORE_GIT_COMMIT,
}


def _resolve_event(event: str | HookEvent) -> HookEvent:
    """Resolve both string and enum event identifiers."""
    if isinstance(event, HookEvent):
        return event
    try:
        return _HOOK_ALIASES.get(event, HookEvent(event))
    except ValueError:
        return event


class HookRegistry:
    """Registry for event hooks with priority-based ordering.

    Lower priority values execute first (default: 1000).
    Within the same priority, hooks execute in registration order.
    """

    DEFAULT_PRIORITY = 1000

    def __init__(self):
        self._hooks: dict[str, list[tuple[int, Callable]]] = {
            e.value: [] for e in HookEvent
        }

    def register(self, event: str | HookEvent, callback: Callable, priority: int = DEFAULT_PRIORITY):
        """Register a callback for an event.

        Args:
            event: HookEvent enum or legacy string name
            callback: Synchronous callable (for async, use AsyncHookRegistry)
            priority: Lower = earlier execution (default 1000)
        """
        event_key = _resolve_event(event).value
        if event_key not in self._hooks:
            self._hooks[event_key] = []
        self._hooks[event_key].append((priority, callback))
        # Keep sorted: lower priority first, stable within same priority
        self._hooks[event_key].sort(key=lambda x: x[0])

    def trigger(self, event: str | HookEvent, *args, **kwargs) -> Any:
        """Trigger all callbacks for an event in priority order.

        Returns the first non-None result (used for blocking operations).
        """
        event_key = _resolve_event(event).value
        for _, callback in self._hooks.get(event_key, []):
            result = callback(*args, **kwargs)
            if result is not None:
                return result
        return None


class AsyncHookRegistry(HookRegistry):
    """Async-aware hook registry — supports both sync and async callbacks.

    Async callbacks are awaited directly. Sync callbacks run in
    the default thread pool executor to avoid blocking.
    """

    def register(self, event: str | HookEvent, callback: Callable, priority: int = HookRegistry.DEFAULT_PRIORITY):
        """Register a callback (sync or async) for an event."""
        super().register(event, callback, priority)

    async def trigger(self, event: str | HookEvent, *args, **kwargs) -> Any:  # type: ignore[override]
        """Trigger all callbacks with async support.

        Returns the first non-None result.
        """
        event_key = _resolve_event(event).value
        for _, callback in self._hooks.get(event_key, []):
            if asyncio.iscoroutinefunction(callback):
                result = await callback(*args, **kwargs)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: callback(*args, **kwargs))
            if result is not None:
                return result
        return None


# Global registries
hook_registry = HookRegistry()
async_hook_registry = AsyncHookRegistry()


# ── Built-in BeforeGitCommit review callback ──────────────────

def _builtin_commit_review(msg: str, file_path: str) -> str | None:
    """Built-in callback: logs commit info so user can review auto-commits.

    Returns None to allow the commit, or a string to block it.
    """
    logger.info("Auto-commit review: message=%s file=%s", msg, file_path)
    return None  # Allow by default — override by registering a blocking callback


# Register the built-in (low priority = runs last, after user hooks)
hook_registry.register(HookEvent.BEFORE_GIT_COMMIT, _builtin_commit_review, priority=2000)
async_hook_registry.register(HookEvent.BEFORE_GIT_COMMIT, _builtin_commit_review, priority=2000)

