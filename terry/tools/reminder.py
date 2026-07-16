"""Reminder tool - manage reminders and schedules (passive registry).

Reminders are parsed and persisted, but there is no background thread or
notification delivery — nothing fires at the scheduled time. The LLM/user must
poll the 'list' action to surface due reminders. Active scheduling is out of
scope here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from ..core.platform_utils import get_terry_dir
from . import BaseTool, tool_registry


class ReminderTool(BaseTool):
    """Manage reminders and schedules (passive — no background thread)."""
    risk_level = "safe"
    category = "task"

    name = "reminder"
    description = (
        "Create, list, and manage reminders. Supports one-time and recurring reminders. "
        "Passive: reminders are stored but never fire on their own — call 'list' "
        "to surface reminders whose time has passed."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "delete", "complete"],
                "description": "Action to perform",
            },
            "title": {
                "type": "string",
                "description": "Reminder title (for add action)",
            },
            "time": {
                "type": "string",
                "description": "Reminder time in ISO format or relative format (e.g., '2026-01-10T14:00:00' or '+2h' for 2 hours from now)",
            },
            "description": {
                "type": "string",
                "description": "Optional reminder description",
            },
            "reminder_id": {
                "type": "string",
                "description": "Reminder ID (for delete/complete actions)",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.reminders_file = get_terry_dir() / "reminders.json"
        self.reminders_file.parent.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        action: str,
        title: str = "",
        time: str = "",
        description: str = "",
        reminder_id: str = "",
    ) -> str:
        """Execute reminder action.

        Args:
            action: Action to perform (add, list, delete, complete)
            title: Reminder title (for add)
            time: Reminder time (for add)
            description: Optional description (for add)
            reminder_id: Reminder ID (for delete/complete)

        Returns:
            Result message
        """
        try:
            reminders = self._load_reminders()

            if action == "add":
                if not title:
                    return "Error: Title is required for add action"

                # Parse time
                reminder_time = self._parse_time(time) if time else datetime.now()

                # Create reminder
                new_id = str(len(reminders) + 1).zfill(4)
                reminder = {
                    "id": new_id,
                    "title": title,
                    "description": description,
                    "time": reminder_time.isoformat(),
                    "created": datetime.now().isoformat(),
                    "completed": False,
                }

                reminders.append(reminder)
                self._save_reminders(reminders)

                return f"✓ Reminder added (ID: {new_id})\n  Title: {title}\n  Time: {reminder_time.strftime('%Y-%m-%d %H:%M')}"

            elif action == "list":
                if not reminders:
                    return "No reminders found"

                # Sort by time
                active = [r for r in reminders if not r["completed"]]
                completed = [r for r in reminders if r["completed"]]

                result = []
                if active:
                    result.append("### Active Reminders")
                    for r in sorted(active, key=lambda x: x["time"]):
                        time_str = datetime.fromisoformat(r["time"]).strftime("%Y-%m-%d %H:%M")
                        result.append(f"- [{r['id']}] {r['title']} (Due: {time_str})")
                        if r.get("description"):
                            result.append(f"  {r['description']}")

                if completed:
                    result.append("\n### Completed")
                    for r in completed[-5:]:  # Show last 5 completed
                        result.append(f"- [✓] {r['title']}")

                return "\n".join(result)

            elif action == "delete":
                if not reminder_id:
                    return "Error: Reminder ID is required for delete action"

                original_count = len(reminders)
                reminders = [r for r in reminders if r["id"] != reminder_id]

                if len(reminders) == original_count:
                    return f"Error: Reminder {reminder_id} not found"

                self._save_reminders(reminders)
                return f"✓ Reminder {reminder_id} deleted"

            elif action == "complete":
                if not reminder_id:
                    return "Error: Reminder ID is required for complete action"

                for r in reminders:
                    if r["id"] == reminder_id:
                        r["completed"] = True
                        r["completed_at"] = datetime.now().isoformat()
                        self._save_reminders(reminders)
                        return f"✓ Reminder {reminder_id} marked as complete"

                return f"Error: Reminder {reminder_id} not found"

            else:
                return f"Error: Unknown action '{action}'"

        except Exception as e:
            return f"Error: {e}"

    def _parse_time(self, time_str: str) -> datetime:
        """Parse time string to datetime.

        Args:
            time_str: Time string (ISO format or relative like '+2h', '+30m', '+1d')

        Returns:
            Parsed datetime
        """
        # Try relative time first
        if time_str.startswith("+"):
            value = int(time_str[1:-1])
            unit = time_str[-1].lower()

            if unit == "m":
                return datetime.now() + timedelta(minutes=value)
            elif unit == "h":
                return datetime.now() + timedelta(hours=value)
            elif unit == "d":
                return datetime.now() + timedelta(days=value)
            elif unit == "w":
                return datetime.now() + timedelta(weeks=value)

        # Try ISO format
        try:
            return datetime.fromisoformat(time_str)
        except ValueError:
            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue

            raise ValueError(f"Unable to parse time: {time_str}")

    def _load_reminders(self) -> list[dict]:
        """Load reminders from file."""
        if not self.reminders_file.exists():
            return []

        try:
            with open(self.reminders_file) as f:
                return json.load(f)
        except Exception:
            return []

    def _save_reminders(self, reminders: list[dict]):
        """Save reminders to file."""
        with open(self.reminders_file, "w") as f:
            json.dump(reminders, f, indent=2)


# Auto-register
tool_registry.register(ReminderTool())
