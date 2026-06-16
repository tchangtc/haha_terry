"""Task Update tool — lets the LLM mark tasks as completed or in progress.

Exposes the TaskManager to the agent's tool set so the LLM can drive
the plan execution loop itself.
"""

from __future__ import annotations

from . import BaseTool, tool_registry


class TaskUpdateTool(BaseTool):
    """Update the status of a task in the active execution plan."""

    name = "task_update"
    description = (
        "Update a task's status in the active plan. "
        "Use to mark a task as completed, in progress, or failed."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the task to update.",
            },
            "status": {
                "type": "string",
                "enum": ["in_progress", "completed", "failed"],
                "description": "New status for the task.",
            },
            "result": {
                "type": "string",
                "description": "Optional summary of what was done.",
            },
        },
        "required": ["task_id", "status"],
    }

    def __init__(self, agent=None):
        self._agent = agent

    def execute(self, task_id: str, status: str, result: str = "") -> str:
        if not self._agent or not hasattr(self._agent, "task_manager"):
            return "Error: Task manager not available."
        tm = self._agent.task_manager
        if not tm or not tm.is_active():
            return "No active plan. Use /plan first."

        if tm.mark(task_id, status, result):
            icon = {"in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(status, "")
            next_task = tm.get_next_ready()
            msg = f"{icon} Task {task_id[:8]} marked {status}."
            if next_task:
                msg += f" Next: {next_task.description[:60]}"
            return msg
        return f"Error: Task {task_id[:8]} not found or invalid status."


def register(agent=None):
    """Register the task_update tool with the global registry."""
    tool = TaskUpdateTool(agent=agent)
    tool_registry.register(tool)
    return tool
