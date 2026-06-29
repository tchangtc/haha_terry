"""Autonomous Pipeline — end-to-end development workflow automation.

Connects the existing autonomous_agent, goal_loop, scheduler, and workflow_v2
into a unified pipeline that can: receive requirements → design → implement →
test → deploy, with minimal human intervention.

Usage:
    from terry.core.auto_pipeline import AutoPipeline
    pipeline = AutoPipeline(agent_factory)
    result = pipeline.run("Build a REST API for user management")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class PipelineStage(StrEnum):
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    IMPLEMENT = "implement"
    TEST = "test"
    REVIEW = "review"
    DEPLOY = "deploy"
    DONE = "done"


STAGE_ORDER = [
    PipelineStage.REQUIREMENTS,
    PipelineStage.DESIGN,
    PipelineStage.IMPLEMENT,
    PipelineStage.TEST,
    PipelineStage.REVIEW,
    PipelineStage.DEPLOY,
]


@dataclass
class PipelineTask:
    """A task at a specific pipeline stage."""

    id: str
    stage: PipelineStage
    description: str
    status: str = "pending"  # pending, running, done, failed, skipped
    output: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0


class AutoPipeline:
    """End-to-end autonomous development pipeline."""

    def __init__(self, agent_factory=None, auto_approve: bool = False):
        self._agent_factory = agent_factory
        self._auto_approve = auto_approve
        self._tasks: list[PipelineTask] = []
        self._counter = 0
        self._paused = False
        self._artifacts: dict[str, str] = {}  # stage → output

    def run(self, requirement: str) -> dict:
        """Run the full autonomous pipeline on a requirement.

        Returns dict with stage outputs and final summary.
        """
        results: dict[str, str] = {}
        context = ""  # Accumulated context passed to each stage

        for stage in STAGE_ORDER:
            if stage == PipelineStage.DONE:
                break
            if self._paused:
                results[stage] = "paused"
                continue

            task = self._create_task(stage, requirement, context)
            self._tasks.append(task)
            self._execute_stage(task, context)

            if task.status == "done":
                context = task.output
                self._artifacts[stage] = task.output
                results[stage] = task.output[:200]
            elif task.status == "failed":
                results[stage] = f"FAILED: {task.error}"
                if not self._auto_approve:
                    break  # Stop pipeline on failure
            else:
                results[stage] = task.status

        results["summary"] = self._build_summary(results)
        return results

    def _create_task(self, stage: PipelineStage, requirement: str,
                     context: str) -> PipelineTask:
        self._counter += 1
        prompts = {
            PipelineStage.REQUIREMENTS: (
                f"Analyze this requirement and produce a structured spec:\n{requirement}"
            ),
            PipelineStage.DESIGN: (
                f"Design the architecture based on these requirements:\n{context[:1000]}\n"
                "Output: API design, data model, component diagram"
            ),
            PipelineStage.IMPLEMENT: (
                f"Implement based on this design:\n{context[:1000]}\n"
                "Write the actual code. Create files as needed."
            ),
            PipelineStage.TEST: (
                f"Write tests for this implementation:\n{context[:1000]}\n"
                "Cover edge cases, error paths, and happy paths."
            ),
            PipelineStage.REVIEW: (
                f"Review this code for bugs, security, and quality:\n{context[:1000]}"
            ),
            PipelineStage.DEPLOY: (
                f"Generate deployment instructions for:\n{context[:500]}"
            ),
        }
        return PipelineTask(
            id=f"pipe-{self._counter}",
            stage=stage,
            description=prompts.get(stage, requirement),
        )

    def _execute_stage(self, task: PipelineTask, context: str):
        """Execute a single pipeline stage."""
        task.status = "running"
        task.started_at = time.time()

        try:
            if self._agent_factory:
                agent = self._agent_factory()
                result = agent.run(task.description)
                task.output = str(result)
                task.status = "done"
            else:
                task.output = f"[passthrough] Stage: {task.stage}"
                task.status = "done"
        except Exception as e:
            task.error = str(e)
            task.status = "failed"

        task.finished_at = time.time()

    @staticmethod
    def _build_summary(results: dict[str, str]) -> str:
        """Build a human-readable pipeline summary."""
        lines = ["# Pipeline Summary\n"]
        for stage in STAGE_ORDER:
            if stage == PipelineStage.DONE:
                continue
            result = results.get(stage, "skipped")
            icon = "✅" if "FAILED" not in result and result != "skipped" else "❌"
            lines.append(f"{icon} **{stage}**: {result[:100]}")
        return "\n".join(lines)

    # ── Control ────────────────────────────────────────────────

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def get_tasks(self, stage: PipelineStage | None = None) -> list[PipelineTask]:
        if stage:
            return [t for t in self._tasks if t.stage == stage]
        return list(self._tasks)

    def get_stats(self) -> dict:
        done = sum(1 for t in self._tasks if t.status == "done")
        failed = sum(1 for t in self._tasks if t.status == "failed")
        return {
            "total_stages": len(self._tasks),
            "done": done,
            "failed": failed,
            "paused": self._paused,
            "auto_approve": self._auto_approve,
            "artifacts": list(self._artifacts.keys()),
        }
