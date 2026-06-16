"""Agentic Task Manager — unified plan execution and task tracking.

Bridges Planner, TodoWrite, and TaskDAG into a single state object that
the Agent loop reads and writes during execution.

Usage:
    tm = TaskManager()
    tm.create_plan("refactor the CLI module", llm_client, tools)
    task = tm.get_next_ready()  # first unblocked pending task
    tm.mark(task.id, "in_progress")
    # ... agent executes ...
    tm.mark(task.id, "completed", "Refactored 3 files")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)

TASK_STATUSES = ("pending", "in_progress", "completed", "failed", "blocked")


@dataclass
class Task:
    """A single task in the execution plan."""
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    description: str = ""
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)
    tool: str = ""
    result: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "depends_on": self.depends_on,
            "tool": self.tool,
            "result": self.result,
        }


class TaskManager:
    """Central task hub that the Agent loop reads/writes during execution.

    Unifies plan steps, todo items, and dependency tracking into one
    state object. Persists to ~/.terry/task_plan.json for resumability.
    """

    STORAGE_FILE = "task_plan.json"

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._goal: str = ""
        self._active: bool = False

    # ── Plan lifecycle ───────────────────────────────────────────

    def create_plan(self, goal: str, steps: list[str], tools: list[str] | None = None) -> list[Task]:
        """Create a new execution plan from a goal and step descriptions.

        Args:
            goal: User's goal description.
            steps: List of step descriptions (from Planner or manual).
            tools: Optional list of available tool names for hinting.

        Returns:
            List of created Task objects.
        """
        self._goal = goal
        self._tasks.clear()
        self._active = True

        tasks = []
        tool_names = tools or []
        for i, step in enumerate(steps):
            # Guess a tool from the description
            guessed_tool = self._guess_tool(step, tool_names)
            task = Task(
                description=step,
                tool=guessed_tool,
            )
            self._tasks[task.id] = task
            tasks.append(task)

        logger.info("Plan created: %d tasks for goal '%s'", len(tasks), goal[:80])
        self._save()
        return tasks

    def is_active(self) -> bool:
        return self._active

    def clear(self) -> None:
        """Reset the task manager state."""
        self._tasks.clear()
        self._goal = ""
        self._active = False

    # ── Task lifecycle ───────────────────────────────────────────

    def get_next_ready(self) -> Task | None:
        """Return the next unblocked pending task, or None."""
        for task in self._tasks.values():
            if task.status != "pending":
                continue
            if self._dependencies_met(task):
                return task
        return None

    def mark(self, task_id: str, status: str, result: str = "") -> bool:
        """Update a task's status and optionally its result.

        Auto-completes downstream tasks that were blocked on this one.
        """
        if task_id not in self._tasks:
            return False
        if status not in TASK_STATUSES:
            return False

        task = self._tasks[task_id]
        task.status = status
        if result:
            task.result = result
        if status == "completed":
            task.completed_at = time.time()

        # Unblock downstream tasks
        if status == "completed":
            for t in self._tasks.values():
                if t.status == "blocked" and self._dependencies_met(t):
                    t.status = "pending"

        self._save()
        return True

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    # ── Queries ──────────────────────────────────────────────────

    def get_summary(self) -> dict[str, int]:
        """Return counts by status."""
        counts = {s: 0 for s in TASK_STATUSES}
        for t in self._tasks.values():
            counts[t.status] = counts.get(t.status, 0) + 1
        return counts

    def to_list(self) -> list[dict[str, Any]]:
        """Return all tasks as dicts for display."""
        return [t.to_dict() for t in self._tasks.values()]

    def to_tool_format(self) -> str:
        """Format current task state for injecting into the system prompt."""
        if not self._tasks:
            return ""
        lines = [f"## Active Plan: {self._goal}" if self._goal else "## Active Plan"]
        for t in self._tasks.values():
            icon = {"pending": "⬜", "in_progress": "🔄", "completed": "✅",
                    "failed": "❌", "blocked": "🔒"}.get(t.status, "❓")
            lines.append(f"{icon} {t.description}" + (f" [{t.tool}]" if t.tool else ""))

        current = self.get_next_ready()
        if current:
            lines.append(f"\nCurrent task: {current.description}")
        return "\n".join(lines)

    def progress_str(self) -> str:
        """Compact progress string: [2/5] ⬜⬜✅🔄⬜"""
        ordered = list(self._tasks.values())
        total = len(ordered)
        done = sum(1 for t in ordered if t.status == "completed")
        icons = "".join(
            {"pending": "⬜", "in_progress": "🔄", "completed": "✅",
             "failed": "❌", "blocked": "🔒"}.get(t.status, "❓")
            for t in ordered
        )
        return f"[{done}/{total}] {icons}" if total > 0 else ""

    # ── Helpers ──────────────────────────────────────────────────

    def _dependencies_met(self, task: Task) -> bool:
        """Check if all dependencies of a task are completed."""
        if not task.depends_on:
            return True
        return all(
            tid in self._tasks and self._tasks[tid].status == "completed"
            for tid in task.depends_on
        )

    @staticmethod
    def _guess_tool(desc: str, available: list[str]) -> str:
        """Guess the most relevant tool from a step description."""
        desc_lower = desc.lower()
        if "read" in desc_lower and "read_file" in available:
            return "read_file"
        if "search" in desc_lower or "grep" in desc_lower:
            return "grep"
        if "write" in desc_lower or "create" in desc_lower:
            return "write_file"
        if "edit" in desc_lower or "modify" in desc_lower or "refactor" in desc_lower:
            return "edit_file"
        if "run" in desc_lower or "test" in desc_lower or "execute" in desc_lower:
            return "bash"
        return ""

    def _save(self) -> None:
        """Persist task state to disk."""
        try:
            path = get_terry_dir(self.STORAGE_FILE)
            data = {
                "goal": self._goal,
                "active": self._active,
                "tasks": [t.to_dict() for t in self._tasks.values()],
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Failed to persist task plan", exc_info=True)

    def load(self) -> bool:
        """Restore task state from disk. Returns True if state was loaded."""
        try:
            path = get_terry_dir(self.STORAGE_FILE)
            if not path.exists():
                return False
            data = json.loads(path.read_text(encoding="utf-8"))
            self._goal = data.get("goal", "")
            self._active = data.get("active", False)
            for td in data.get("tasks", []):
                task = Task(
                    id=td["id"], description=td["description"],
                    status=td.get("status", "pending"),
                    depends_on=td.get("depends_on", []),
                    tool=td.get("tool", ""), result=td.get("result", ""),
                )
                self._tasks[task.id] = task
            logger.info("Task plan loaded: %d tasks", len(self._tasks))
            return True
        except Exception:
            logger.debug("Failed to load task plan", exc_info=True)
            return False
