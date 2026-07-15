"""Harness Tool — exposes the orchestration engine to the Agent."""

from __future__ import annotations

import json

from ..core.harness import HarnessEngine, HarnessPattern
from . import BaseTool, tool_registry


class HarnessTool(BaseTool):
    """Exposes the HarnessEngine as an Agent tool.

    Lets the LLM programmatically orchestrate sub-agents using
    8 patterns directly from conversation.
    """

    risk_level = "safe"
    category = "general"

    name = "harness"
    description = (
        "Execute complex multi-step tasks using sub-agents. Supports 8 patterns: "
        "sequential (A→B→C), parallel (A‖B‖C), fan-out-merge (split→parallel→combine), "
        "adversarial-verify (generate→verify→fix), tournament (compare→best wins), "
        "classify-execute (classify→route→execute), loop-until-done (iterate→score→repeat), "
        "generate-filter (generate→score→deduplicate). "
        "Use this for large tasks that benefit from parallel execution or comparative analysis."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "enum": [p.value for p in HarnessPattern],
                "description": "Orchestration pattern to use",
            },
            "prompts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of task prompts to execute",
            },
            "goals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "High-level goals (for merge/tournament patterns)",
            },
        },
        "required": ["pattern"],
    }

    def __init__(self, harness: HarnessEngine | None = None):
        self._harness = harness

    def bind(self, harness: HarnessEngine) -> None:
        """Attach the agent's factory-backed HarnessEngine so the 8 patterns
        can actually spawn sub-agents. Without this, patterns degrade to
        placeholders (no agent_factory available)."""
        self._harness = harness

    def execute(
        self,
        pattern: str = "sequential",
        prompts: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> str:
        # An agent-bound harness (with a real agent_factory) is required for the
        # patterns to run sub-agents; a bare HarnessEngine() would only emit
        # placeholders, so we surface that explicitly instead of faking success.
        if self._harness is None:
            return (
                "Error: harness engine not bound to an agent. "
                "Sub-agent orchestration is unavailable in this context."
            )
        try:
            result = self._harness.execute(
                pattern=pattern,
                prompts=prompts or [],
                goals=goals or [],
            )
            return json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error: {e}"


def register(agent) -> None:
    """Bind the HarnessTool to the agent's factory-backed HarnessEngine.

    Mirrors the slash_command/task_update pattern: the tool auto-registers a
    placeholder in discover_tools(), then the Agent re-binds it once its own
    HarnessEngine (with a real agent_factory) exists.
    """
    harness = getattr(agent, "harness", None)
    if harness is None:
        return
    for tool in tool_registry.list_tools():
        if isinstance(tool, HarnessTool):
            tool.bind(harness)
            return
    tool = HarnessTool(harness=harness)
    tool_registry.register(tool)


# Auto-register via discover_tools()
tool_registry.register(HarnessTool())
