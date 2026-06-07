"""Persistent task DAG - dependency-aware task management across sessions.

Tasks form a directed acyclic graph with dependencies, status tracking,
and Mermaid diagram export.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from .platform_utils import get_terry_dir


class TaskNode:
    """A single task in the DAG."""

    def __init__(
        self,
        task_id: str,
        description: str,
        depends_on: list[str] | None = None,
        status: str = "pending",
        assignee: str = "",
        tags: list[str] | None = None,
    ):
        self.id = task_id
        self.description = description
        self.depends_on = depends_on or []
        self.status = status  # pending, in_progress, completed, failed, blocked
        self.assignee = assignee
        self.tags = tags or []
        self.result: str | None = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "depends_on": self.depends_on,
            "status": self.status,
            "assignee": self.assignee,
            "tags": self.tags,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskNode:
        node = cls(
            task_id=data["id"],
            description=data["description"],
            depends_on=data.get("depends_on", []),
            status=data.get("status", "pending"),
            assignee=data.get("assignee", ""),
            tags=data.get("tags", []),
        )
        node.result = data.get("result")
        node.created_at = data.get("created_at", "")
        node.updated_at = data.get("updated_at", "")
        return node


class TaskDAG:
    """Manages a persistent directed acyclic graph of tasks."""

    MAX_TASKS = 200

    def __init__(self, path: Path | None = None):
        self.path = path or get_terry_dir() / "tasks.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, TaskNode] = {}
        self._load()

    def _load(self) -> None:
        """Load tasks from disk."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.tasks = {
                    tid: TaskNode.from_dict(d)
                    for tid, d in data.get("tasks", {}).items()
                }
            except Exception:
                self.tasks = {}

    def _save(self) -> None:
        """Persist tasks to disk."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
        }
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_task(
        self,
        description: str,
        depends_on: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Add a new task. Returns task ID."""
        if len(self.tasks) >= self.MAX_TASKS:
            self._prune_completed()

        task_id = f"task_{int(time.time() * 1000)}"
        node = TaskNode(
            task_id=task_id,
            description=description,
            depends_on=depends_on or [],
            tags=tags or [],
        )
        self.tasks[task_id] = node
        self._save()
        return task_id

    def get_next_ready(self, limit: int = 5) -> list[TaskNode]:
        """Get tasks that are ready to execute (dependencies satisfied)."""
        ready = []
        for task in self.tasks.values():
            if task.status not in ("pending",):
                continue
            if not task.depends_on:
                ready.append(task)
                continue
            all_done = all(
                self.tasks.get(d) and self.tasks[d].status == "completed"
                for d in task.depends_on
            )
            if all_done:
                ready.append(task)
        return sorted(ready, key=lambda t: t.created_at)[:limit]

    def mark_status(self, task_id: str, status: str, result: str | None = None) -> bool:
        """Update a task's status."""
        if task_id not in self.tasks:
            return False
        self.tasks[task_id].status = status
        self.tasks[task_id].updated_at = datetime.now().isoformat()
        if result:
            self.tasks[task_id].result = result
        self._save()
        return True

    def get_blocked_tasks(self) -> list[TaskNode]:
        """Get tasks that are blocked by unfinished dependencies."""
        blocked = []
        for task in self.tasks.values():
            if task.status not in ("pending",):
                continue
            if any(
                d not in self.tasks or
                self.tasks[d].status in ("failed", "pending")
                for d in task.depends_on
            ):
                blocked.append(task)
        return blocked

    def get_critical_path(self) -> list[TaskNode]:
        """Estimate critical path (longest chain of dependencies)."""
        # Simple greedy: start from tasks with no dependents
        in_degree: dict[str, int] = {tid: 0 for tid in self.tasks}
        for task in self.tasks.values():
            for dep in task.depends_on:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        # BFS from root tasks
        roots = [tid for tid, deg in in_degree.items() if deg == 0]
        if not roots:
            return []

        visited = set()
        path = []
        queue = roots[:]

        while queue:
            tid = queue.pop(0)
            if tid in visited:
                continue
            visited.add(tid)
            if tid in self.tasks:
                path.append(self.tasks[tid])
            # Find tasks that depend on this one
            for task in self.tasks.values():
                if tid in task.depends_on and task.id not in visited:
                    queue.append(task.id)

        return path

    def to_mermaid(self) -> str:
        """Export the task DAG as a Mermaid diagram."""
        lines = ["```mermaid", "graph TD"]
        for task in self.tasks.values():
            status_emoji = {
                "pending": "⏳", "in_progress": "🔄",
                "completed": "✅", "failed": "❌", "blocked": "🔒",
            }.get(task.status, "❓")
            safe_id = task.id.replace("-", "_").replace(".", "_")
            desc = task.description[:50]
            lines.append(
                f'    {safe_id}["{status_emoji} {desc}"]'
            )
            for dep in task.depends_on:
                safe_dep = dep.replace("-", "_").replace(".", "_")
                lines.append(f"    {safe_dep} --> {safe_id}")
        lines.append("```")
        return "\n".join(lines)

    def list_by_status(self, status: str) -> list[TaskNode]:
        """List tasks by status."""
        return [
            t for t in self.tasks.values() if t.status == status
        ]

    def _prune_completed(self) -> int:
        """Remove completed tasks to free space."""
        to_remove = [
            tid for tid, t in self.tasks.items()
            if t.status == "completed"
        ][:50]  # Remove up to 50 at a time
        for tid in to_remove:
            del self.tasks[tid]
        if to_remove:
            self._save()
        return len(to_remove)

    def get_summary(self) -> dict[str, int]:
        """Get task count summary by status."""
        summary = {}
        for task in self.tasks.values():
            summary[task.status] = summary.get(task.status, 0) + 1
        return summary
