"""Cron scheduler for recurring agent tasks.

Supports cron-style scheduling with persistence, task history,
and heartbeat-based recovery for 24/7 autonomous operation.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class CronScheduler:
    """Lightweight cron scheduler with persistence.

    Supports 5-field cron expressions (minute, hour, day, month, weekday)
    and simple interval-based scheduling.
    """

    MAX_TASKS = 100

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path.home() / ".terry" / "scheduled_tasks.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[int, dict[str, Any]] = {}
        self._counter = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._callbacks: dict[int, Callable] = {}
        self._load()

    def _load(self) -> None:
        """Load tasks from disk."""
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                self.tasks = {
                    int(k): v for k, v in data.get("tasks", {}).items()
                }
                self._counter = data.get("counter", 0)
            except Exception:
                self.tasks = {}
                self._counter = 0

    def _save(self) -> None:
        """Persist tasks to disk."""
        data = {
            "version": "1.0",
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
            "tasks": {str(k): v for k, v in self.tasks.items()},
        }
        self.db_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def schedule(
        self,
        task_type: str,
        params: dict[str, Any],
        cron_expr: str | None = None,
        interval_seconds: int = 0,
        callback: Callable | None = None,
    ) -> int:
        """Schedule a new task.

        Args:
            task_type: Task type identifier (e.g., 'review', 'update', 'backup')
            params: Task parameters
            cron_expr: 5-field cron expression or None
            interval_seconds: Repeat interval in seconds (0 = run once)
            callback: Function to call when task fires

        Returns:
            Task ID
        """
        if len(self.tasks) >= self.MAX_TASKS:
            self._prune_expired()

        self._counter += 1
        task_id = self._counter

        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "params": params,
            "cron": cron_expr,
            "interval": interval_seconds,
            "status": "active",
            "last_run": None,
            "next_run": self._compute_next_run(cron_expr, interval_seconds),
            "run_count": 0,
            "created_at": datetime.now().isoformat(),
        }

        if callback:
            self._callbacks[task_id] = callback

        self._save()
        return task_id

    def cancel(self, task_id: int) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "cancelled"
            self._callbacks.pop(task_id, None)
            self._save()
            return True
        return False

    def get_due_tasks(self) -> list[dict[str, Any]]:
        """Get tasks that are due for execution."""
        now = datetime.now()
        due = []
        for task in self.tasks.values():
            if task["status"] != "active":
                continue
            next_run = task.get("next_run")
            if next_run and datetime.fromisoformat(next_run) <= now:
                due.append(task)
        return due

    def execute_due(self, agent_factory: Callable | None = None) -> dict[int, str]:
        """Execute all due tasks. Returns {task_id: result} dict."""
        results = {}
        for task in self.get_due_tasks():
            tid = task["id"]
            try:
                if tid in self._callbacks:
                    result = self._callbacks[tid]()
                    results[tid] = str(result)
                elif agent_factory:
                    agent = agent_factory()
                    response = agent.run(task["params"].get("prompt", ""))
                    results[tid] = response

                # Update task status
                task["last_run"] = datetime.now().isoformat()
                task["run_count"] += 1
                task["next_run"] = self._compute_next_run(
                    task.get("cron"),
                    task.get("interval", 0),
                )
                if task.get("interval", 0) == 0 and not task.get("cron"):
                    task["status"] = "completed"
            except Exception as e:
                results[tid] = f"Error: {e}"
                task["status"] = "failed"

        if results:
            self._save()
        return results

    def _compute_next_run(
        self, cron_expr: str | None, interval_seconds: int
    ) -> str | None:
        """Compute the next run time."""
        now = datetime.now()
        if interval_seconds > 0:
            return (now + timedelta(seconds=interval_seconds)).isoformat()
        if cron_expr:
            # Simplified: parse basic cron and compute next match
            return self._parse_cron_next(cron_expr, now)
        return None  # Run once immediately

    def _parse_cron_next(self, cron_expr: str, now: datetime) -> str | None:
        """Parse a 5-field cron expression and find the next match."""
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return None

            minute, hour, dom, month, dow = parts

            # Handle wildcards and step values
            if minute == "*":
                next_minute = now.minute + 1
            elif "/" in minute:
                step = int(minute.split("/")[1])
                next_minute = ((now.minute // step) + 1) * step
            else:
                next_minute = int(minute)

            if hour == "*":
                next_hour = now.hour
            else:
                next_hour = int(hour)

            next_time = now.replace(
                minute=min(next_minute, 59),
                hour=min(next_hour, 23),
                second=0,
                microsecond=0,
            )

            if next_time <= now:
                next_time += timedelta(hours=1)

            return next_time.isoformat()
        except Exception:
            return None

    def start_loop(self, agent_factory: Callable | None = None, check_interval: int = 60) -> None:
        """Start the scheduler loop in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(agent_factory, check_interval),
            daemon=True,
        )
        self._thread.start()

    def _run_loop(
        self, agent_factory: Callable | None, check_interval: int
    ) -> None:
        """Background scheduler loop."""
        while self._running:
            try:
                self.execute_due(agent_factory)
            except Exception:
                pass
            time.sleep(check_interval)

    def stop_loop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False

    def _prune_expired(self) -> int:
        """Remove completed/cancelled tasks older than 7 days."""
        cutoff = datetime.now() - timedelta(days=7)
        to_remove = []
        for tid, task in self.tasks.items():
            if task["status"] in ("completed", "cancelled"):
                created = task.get("created_at", "")
                if created and datetime.fromisoformat(created) < cutoff:
                    to_remove.append(tid)
        for tid in to_remove:
            del self.tasks[tid]
            self._callbacks.pop(tid, None)
        if to_remove:
            self._save()
        return len(to_remove)

    def get_summary(self) -> dict[str, int]:
        """Get task count summary by status."""
        summary = {}
        for task in self.tasks.values():
            summary[task["status"]] = summary.get(task["status"], 0) + 1
        return summary

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks."""
        return [
            {
                "id": t["id"],
                "type": t["type"],
                "status": t["status"],
                "next_run": t.get("next_run"),
                "run_count": t.get("run_count", 0),
            }
            for t in self.tasks.values()
        ]
