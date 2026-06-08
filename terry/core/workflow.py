"""Workflow engine - declarative multi-step agent pipelines.

Supports YAML-defined workflows with sequential stages, parallel branches,
and conditional execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .typing_protocols import AgentLike


class WorkflowStep:
    """A single step in a workflow."""

    def __init__(
        self,
        name: str,
        tool: str = "",
        prompt: str = "",
        depends_on: list[str] | None = None,
        condition: str | None = None,
        max_retries: int = 1,
    ):
        self.name = name
        self.tool = tool
        self.prompt = prompt
        self.depends_on = depends_on or []
        self.condition = condition
        self.max_retries = max_retries

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowStep:
        return cls(
            name=data.get("name", "unnamed"),
            tool=data.get("tool", ""),
            prompt=data.get("prompt", ""),
            depends_on=data.get("depends_on", []),
            condition=data.get("condition"),
            max_retries=data.get("max_retries", 1),
        )


class Workflow:
    """A reusable, declarative workflow definition."""

    def __init__(
        self,
        name: str,
        description: str = "",
        steps: list[WorkflowStep] | None = None,
    ):
        self.name = name
        self.description = description
        self.steps = steps or []

    @classmethod
    def from_yaml(cls, path: Path) -> Workflow:
        """Load a workflow from a YAML file."""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        steps = [
            WorkflowStep.from_dict(s) for s in data.get("steps", [])
        ]
        return cls(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            steps=steps,
        )

    def to_yaml(self) -> str:
        """Serialize workflow to YAML string."""
        return yaml.dump({
            "name": self.name,
            "description": self.description,
            "steps": [
                {
                    "name": s.name,
                    "tool": s.tool,
                    "prompt": s.prompt,
                    "depends_on": s.depends_on,
                    "condition": s.condition,
                    "max_retries": s.max_retries,
                }
                for s in self.steps
            ],
        })


class WorkflowEngine:
    """Executes declarative workflows using the Terry agent.

    Supports sequential, parallel, and conditional step execution
    with retry logic and result propagation.
    """

    def __init__(self, agent: AgentLike | None = None):
        self.agent = agent
        self.results: dict[str, Any] = {}

    def execute(self, workflow: Workflow, context: dict | None = None) -> dict[str, Any]:
        """Execute a workflow and return results for each step.

        Args:
            workflow: Workflow to execute
            context: Optional variables to inject

        Returns:
            Dict mapping step names to results
        """
        self.results = {}
        completed: set[str] = set()
        failed: set[str] = set()
        retries: dict[str, int] = {}

        while len(completed) + len(failed) < len(workflow.steps):
            progress_made = False

            for step in workflow.steps:
                if step.name in completed or step.name in failed:
                    continue

                # Check dependencies
                deps_satisfied = all(
                    d in completed for d in step.depends_on
                )
                if not deps_satisfied:
                    continue

                # Check condition
                if step.condition:
                    cond_result = self._evaluate_condition(
                        step.condition, context or {}
                    )
                    if not cond_result:
                        completed.add(step.name)
                        self.results[step.name] = "Skipped (condition false)"
                        progress_made = True
                        continue

                # Execute step
                try:
                    result = self._execute_step(step)
                    self.results[step.name] = result
                    completed.add(step.name)
                    progress_made = True
                except Exception as e:
                    retries[step.name] = retries.get(step.name, 0) + 1
                    if retries[step.name] <= step.max_retries:
                        continue
                    self.results[step.name] = f"Error: {e}"
                    failed.add(step.name)
                    progress_made = True

            if not progress_made:
                # Deadlock detected
                for step in workflow.steps:
                    if step.name not in completed and step.name not in failed:
                        self.results[step.name] = "Error: Deadlocked (unmet dependency)"
                        failed.add(step.name)
                break

        return self.results

    def _execute_step(self, step: WorkflowStep) -> str:
        """Execute a single workflow step."""
        if not self.agent:
            return f"Would execute: {step.prompt}"

        try:
            if step.tool:
                result = self.agent.tools.execute(step.tool, **{"prompt": step.prompt})
                return str(result)
            elif step.prompt:
                result = self.agent.run(step.prompt)
                return str(result)
            return "No action specified"
        except Exception:
            raise

    def _evaluate_condition(
        self, condition: str, context: dict
    ) -> bool:
        """Evaluate a simple condition string.

        Supports: 'var_name == value', 'var_name != value', 'var_name'
        """
        if "==" in condition:
            var, val = condition.split("==", 1)
            return str(context.get(var.strip(), "")).strip() == val.strip()
        if "!=" in condition:
            var, val = condition.split("!=", 1)
            return str(context.get(var.strip(), "")).strip() != val.strip()
        return bool(context.get(condition.strip()))
