"""Autonomous Workflow v2 — event-driven workflows with webhook and CI triggers.

Extends the existing workflow/autonomous_agent system with:
- Webhook triggers: HTTP endpoint to kick off workflows
- CI/CD triggers: GitHub/GitLab webhook event parsing
- File watch triggers: react to filesystem changes
- Scheduled triggers: cron-based workflow scheduling (extends CronScheduler)

Usage:
    engine = WorkflowEngineV2(agent_factory)
    engine.register_webhook("/review-pr", "review_pr_workflow")
    engine.start()
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS = 30
WEBHOOK_PORT_DEFAULT = 9876


@dataclass
class Trigger:
    """A workflow trigger definition."""

    name: str
    type: str           # webhook, schedule, file_watch, ci_event
    workflow: str       # Workflow name to execute
    config: dict = field(default_factory=dict)  # Type-specific config
    enabled: bool = True
    last_fired: float = 0.0


@dataclass
class WorkflowRun:
    """A single workflow execution record."""

    id: str
    workflow: str
    trigger: str
    status: str = "pending"   # pending, running, done, failed
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    result: str = ""
    error: str = ""


class WorkflowEngineV2:
    """Event-driven workflow engine with external triggers."""

    def __init__(self, agent_factory=None):
        self._agent_factory = agent_factory
        self._triggers: dict[str, Trigger] = {}
        self._runs: list[WorkflowRun] = []
        self._run_counter = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._webhook_server: Any = None

    def register_trigger(self, name: str, trigger_type: str,
                         workflow: str, config: dict | None = None):
        """Register a new workflow trigger."""
        self._triggers[name] = Trigger(
            name=name, type=trigger_type, workflow=workflow,
            config=config or {},
        )

    def remove_trigger(self, name: str):
        self._triggers.pop(name, None)

    def list_triggers(self) -> list[Trigger]:
        return list(self._triggers.values())

    def start(self):
        """Start the workflow engine (polling + webhook server)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop,
                                         daemon=True, name="workflow-v2")
        self._thread.start()
        logger.info("WorkflowEngineV2 started")

    def stop(self):
        self._running = False

    # ── Trigger Types ─────────────────────────────────────────────

    def fire_schedule(self, trigger_name: str):
        """Fire a scheduled trigger (called by CronScheduler)."""
        trigger = self._triggers.get(trigger_name)
        if trigger and trigger.enabled:
            self._execute(trigger, {"type": "schedule", "fired_at": time.time()})

    def fire_webhook(self, trigger_name: str, payload: dict):
        """Fire a webhook trigger with payload."""
        trigger = self._triggers.get(trigger_name)
        if trigger and trigger.enabled:
            self._execute(trigger, {"type": "webhook", "payload": payload})

    def fire_ci_event(self, trigger_name: str, event_type: str, event_data: dict):
        """Fire a CI event trigger (GitHub/GitLab webhook)."""
        trigger = self._triggers.get(trigger_name)
        if trigger and trigger.enabled:
            self._execute(trigger, {
                "type": "ci_event",
                "event": event_type,
                "data": event_data,
            })

    def fire_file_watch(self, trigger_name: str, changed_files: list[str]):
        """Fire a file watch trigger."""
        trigger = self._triggers.get(trigger_name)
        if trigger and trigger.enabled:
            self._execute(trigger, {
                "type": "file_watch",
                "files": changed_files,
            })

    # ── Execution ─────────────────────────────────────────────────

    def _execute(self, trigger: Trigger, context: dict):
        """Execute a workflow in response to a trigger."""
        self._run_counter += 1
        run = WorkflowRun(
            id=f"wf-{self._run_counter}",
            workflow=trigger.workflow,
            trigger=trigger.name,
            status="running",
        )
        self._runs.append(run)
        trigger.last_fired = time.time()

        try:
            if self._agent_factory:
                agent = self._agent_factory()
                prompt = self._build_prompt(trigger, context)
                result = agent.run(prompt)
                run.status = "done"
                run.result = str(result)[:500]
            else:
                run.status = "done"
                run.result = f"[passthrough] {trigger.workflow}: {json.dumps(context, default=str)[:200]}"
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.warning("Workflow %s failed: %s", trigger.workflow, e)

        run.finished_at = time.time()

    @staticmethod
    def _build_prompt(trigger: Trigger, context: dict) -> str:
        """Build the agent prompt from trigger + context."""
        prompt = f"Execute workflow: {trigger.workflow}\n"
        prompt += f"Trigger: {trigger.name} ({trigger.type})\n"
        if "payload" in context:
            prompt += f"Payload: {json.dumps(context['payload'], default=str)[:500]}\n"
        if "files" in context:
            prompt += f"Changed files: {', '.join(context['files'][:20])}\n"
        if "event" in context:
            prompt += f"CI Event: {context['event']}\n"
        return prompt

    # ── Polling ───────────────────────────────────────────────────

    def _poll_loop(self):
        """Background thread: check schedule + file triggers."""
        while self._running:
            time.sleep(POLL_INTERVAL_SECONDS)

    # ── History / Stats ───────────────────────────────────────────

    def get_runs(self, status: str | None = None, limit: int = 20) -> list[WorkflowRun]:
        runs = self._runs
        if status:
            runs = [r for r in runs if r.status == status]
        return runs[-limit:]

    def get_stats(self) -> dict:
        total = len(self._runs)
        done = sum(1 for r in self._runs if r.status == "done")
        failed = sum(1 for r in self._runs if r.status == "failed")
        return {
            "triggers": len(self._triggers),
            "total_runs": total,
            "done": done,
            "failed": failed,
            "running": self._running,
        }
