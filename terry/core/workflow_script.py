"""WorkflowScript — Python DSL for composing orchestration patterns.

Wraps DynamicWorkflowEngine patterns into a fluent, chainable API.
Each method maps to an existing DynamicWorkflowEngine._run_* implementation.

Usage:
    wf = WorkflowScript("audit security")
    wf.fan_out(["scan secrets", "check deps", "audit auth"])
    wf.verify(adversarial=3)
    wf.synthesize()
    results = wf.run(agent_factory)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern

logger = logging.getLogger(__name__)


class WorkflowScriptError(Exception):
    """Raised on invalid script composition."""


@dataclass
class WorkflowScript:
    """Fluent DSL for building and executing multi-agent orchestration scripts.

    Each chainable method selects a WorkflowPattern and accumulates stages.
    Call run() to execute with a given agent factory.
    """

    name: str = ""
    _stages: list[dict[str, Any]] = field(default_factory=list)
    _pattern: WorkflowPattern | None = None
    _verifiers: int = 0
    _max_iterations: int = 5

    # ── Pattern methods ─────────────────────────────────────────────

    def fan_out(self, tasks: list[str]) -> WorkflowScript:
        """Split work into parallel subtasks, then merge results."""
        self._pattern = WorkflowPattern.FAN_OUT_MERGE
        self._stages = [{"name": f"task_{i}", "prompt": t} for i, t in enumerate(tasks)]
        self._stages.append({"name": "merge", "prompt": "Combine all results into a cohesive answer."})
        return self

    def classify_execute(self, task: str, handlers: list[str]) -> WorkflowScript:
        """Classify the task, then route to a specialized handler."""
        self._pattern = WorkflowPattern.CLASSIFY_EXECUTE
        self._stages = [{"name": "classify", "prompt": f"Classify this task: {task}"}]
        for i, h in enumerate(handlers):
            self._stages.append({"name": f"handler_{i}", "prompt": h})
        return self

    def verify(self, adversarial: int = 3) -> WorkflowScript:
        """Add adversarial verification (default 3 independent verifiers)."""
        self._pattern = WorkflowPattern.ADVERSARIAL_VERIFY
        self._verifiers = adversarial
        if self._stages:
            self._stages[-1]["verify"] = True
        return self

    def tournament(self, approaches: list[str]) -> WorkflowScript:
        """Run N approaches in parallel, pairwise compare, pick best."""
        self._pattern = WorkflowPattern.TOURNAMENT
        for i, a in enumerate(approaches):
            self._stages.append({"name": f"contestant_{i}", "prompt": a})
        self._stages.append({"name": "judge", "prompt": "Compare and rank the solutions."})
        return self

    def loop_until_done(self, task: str, max_iterations: int = 5) -> WorkflowScript:
        """Repeat generate→evaluate→refine until quality threshold is met."""
        self._pattern = WorkflowPattern.LOOP_UNTIL_DONE
        self._stages = [
            {"name": "attempt", "prompt": task},
            {"name": "evaluate", "prompt": "Evaluate quality of the solution."},
        ]
        self._max_iterations = max_iterations
        return self

    def generate_filter(self, topic: str, count: int = 10) -> WorkflowScript:
        """Generate ideas, deduplicate, return top-N."""
        self._pattern = WorkflowPattern.GENERATE_FILTER
        self._stages = [{"name": "generate", "prompt": f"Generate ideas for: {topic}"}]
        self._stages.append({"name": "filter", "prompt": f"Deduplicate and return top {count}."})
        return self

    def synthesize(self) -> WorkflowScript:
        """Add a final synthesis step."""
        self._stages.append({
            "name": "synthesize",
            "prompt": "Synthesize all results into a final answer.",
        })
        return self

    # ── Execution ───────────────────────────────────────────────────

    def run(
        self,
        agent_factory: Callable,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the composed workflow.

        Args:
            agent_factory: Callable that returns an agent-like instance.
            context: Optional context variables.

        Returns:
            Dict mapping stage_id to result string.
        """
        if not self._pattern:
            raise WorkflowScriptError(
                "No pattern configured. Call fan_out(), verify(), etc. before run()."
            )

        engine = DynamicWorkflowEngine(agent_factory=agent_factory)

        from .dynamic_workflow import DynamicWorkflow
        wf = DynamicWorkflow(
            name=self.name or f"script_{uuid.uuid4().hex[:6]}",
            goal=self.name,
            pattern=self._pattern,
        )
        wf.stages = self._stages

        logger.info("Running workflow script: %s with pattern %s", self.name, self._pattern.value)
        return engine.execute(wf, context=context)
