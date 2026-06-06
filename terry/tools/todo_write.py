"""Todo write tool - manage task lists."""

from __future__ import annotations

import json
from pathlib import Path

from . import BaseTool, tool_registry


class TodoWriteTool(BaseTool):
    """Create and manage todo lists for tracking tasks."""

    name = "todo_write"
    description = "Create or update a todo list. Use this to track tasks and their status."
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "List of todo items",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Task description",
                        },
                        "status": {
                            "type": "string",
                            "description": "Task status",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["todos"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self._todos: list[dict] = []

    def execute(self, todos: list[dict]) -> str:
        """Update todo list."""
        try:
            # Validate todos
            for i, todo in enumerate(todos):
                if not isinstance(todo, dict):
                    return f"Error: todos[{i}] must be an object"
                if "content" not in todo or "status" not in todo:
                    return f"Error: todos[{i}] missing 'content' or 'status'"
                if todo["status"] not in ("pending", "in_progress", "completed"):
                    return f"Error: todos[{i}] has invalid status '{todo['status']}'"

            # Update todos
            self._todos = todos

            # Format output
            lines = ["\n📋 Current Tasks:"]
            for i, todo in enumerate(self._todos, 1):
                status_icon = {
                    "pending": "⬜",
                    "in_progress": "🔄",
                    "completed": "✅",
                }.get(todo["status"], "❓")
                lines.append(f"{i}. {status_icon} {todo['content']}")

            # Save to file
            todo_file = self.workdir / ".terry_todos.json"
            with open(todo_file, "w") as f:
                json.dump(self._todos, f, indent=2)

            return "\n".join(lines)

        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(TodoWriteTool())
