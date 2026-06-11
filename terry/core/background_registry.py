"""Central background task registry for tracking all async/parallel tasks.

All parallel execution systems (SubAgentManager, AsyncSubAgentManager,
HarnessEngine, DynamicWorkflowEngine) register their tasks here so the CLI
and WebUI can provide unified monitoring.

Usage:
    registry = get_background_registry()
    registry.register(BackgroundTask(
        description="audit security patterns",
        system="subagent",
        status="running",
    ))
    registry.update(task_id, status="completed", result="Found 3 issues")
    registry.list() -> list of tasks, newest first
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BackgroundTask:
    """A tracked background task across any parallel execution system."""

    id: str = field(default_factory=lambda: f"bg_{uuid.uuid4().hex[:8]}")
    description: str = ""
    system: str = ""          # "subagent" | "async_subagent" | "harness" | "workflow" | "autonomous"
    status: str = "pending"   # pending | running | completed | failed | cancelled
    result: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise for JSON/API output."""
        return {
            "id": self.id,
            "description": self.description[:120],
            "system": self.system,
            "status": self.status,
            "result": self.result[:500] if self.result else None,
            "error": self.error[:500] if self.error else None,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "completed_at": (
                datetime.fromtimestamp(self.completed_at).isoformat()
                if self.completed_at else None
            ),
        }


class BackgroundTaskRegistry:
    """Thread-safe central registry for background tasks.

    All parallel execution subsystems register their tasks here.
    Singleton pattern — use get_background_registry().
    """

    DEFAULT_MAX_COMPLETED_AGE = 3600  # 1 hour

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._lock = threading.RLock()

    def register(self, task: BackgroundTask) -> str:
        """Register a task. Returns task ID."""
        with self._lock:
            self._tasks[task.id] = task
            logger.debug("Registered background task: %s (%s)", task.id, task.system)
            return task.id

    def update(self, task_id: str, **kwargs: Any) -> bool:
        """Update task fields (status, result, error, description).

        Returns True if task was found and updated.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            if kwargs.get("status") in ("completed", "failed", "cancelled"):
                task.completed_at = time.time()
            return True

    def get(self, task_id: str) -> BackgroundTask | None:
        """Get a single task by ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def list(
        self,
        status: str | None = None,
        system: str | None = None,
        limit: int = 50,
    ) -> list[BackgroundTask]:
        """List tasks, filtered by status and/or system, newest first.

        Args:
            status: Filter by status ("running", "completed", etc.). None = all.
            system: Filter by system ("subagent", "harness", etc.). None = all.
            limit: Maximum number of tasks to return.
        """
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if system:
            tasks = [t for t in tasks if t.system == system]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def cancel(self, task_id: str) -> bool:
        """Mark a task as cancelled.

        Note: actual cancellation must be handled by the owning system.
        This only updates the registry. Returns True if task was found.
        """
        return self.update(task_id, status="cancelled")

    def clear_completed(self, max_age: float = DEFAULT_MAX_COMPLETED_AGE) -> int:
        """Remove completed tasks older than max_age seconds. Returns count removed."""
        now = time.time()
        to_remove: list[str] = []
        with self._lock:
            for tid, task in self._tasks.items():
                if task.status in ("completed", "failed", "cancelled") and task.completed_at:
                    if now - task.completed_at > max_age:
                        to_remove.append(tid)
            for tid in to_remove:
                del self._tasks[tid]
        if to_remove:
            logger.debug("Cleared %d completed background tasks", len(to_remove))
        return len(to_remove)


# ── Singleton management ─────────────────────────────────────────

_registry_instance: BackgroundTaskRegistry | None = None


def get_background_registry() -> BackgroundTaskRegistry:
    """Get or create the global BackgroundTaskRegistry (singleton)."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = BackgroundTaskRegistry()
    return _registry_instance


def set_background_registry(instance: BackgroundTaskRegistry) -> None:
    """Inject a custom registry instance (for testing/DI)."""
    global _registry_instance
    _registry_instance = instance
