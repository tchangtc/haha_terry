"""Timer tool - Pomodoro and countdown timer."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from ..core.platform_utils import get_terry_dir
from . import BaseTool, tool_registry


class TimerTool(BaseTool):
    """Manage timers and Pomodoro sessions."""

    name = "timer"
    description = "Start timers, Pomodoro sessions, and track time."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "pomodoro", "list", "stop"],
                "description": "Action to perform",
            },
            "duration": {
                "type": "string",
                "description": "Timer duration (e.g., '25m', '1h30m', '90s')",
            },
            "label": {
                "type": "string",
                "description": "Optional label for the timer",
            },
            "timer_id": {
                "type": "string",
                "description": "Timer ID (for stop action)",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.timers_file = get_terry_dir() / "timers.json"
        self.timers_file.parent.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        action: str,
        duration: str = "",
        label: str = "",
        timer_id: str = "",
    ) -> str:
        """Execute timer action.

        Args:
            action: Action to perform (start, pomodoro, list, stop)
            duration: Timer duration (for start)
            label: Optional label (for start/pomodoro)
            timer_id: Timer ID (for stop)

        Returns:
            Result message
        """
        try:
            timers = self._load_timers()

            if action == "start":
                if not duration:
                    return "Error: Duration is required for start action"

                # Parse duration
                seconds = self._parse_duration(duration)
                if seconds <= 0:
                    return "Error: Invalid duration format"

                # Create timer
                new_id = str(len(timers) + 1).zfill(4)
                end_time = datetime.now() + timedelta(seconds=seconds)

                timer = {
                    "id": new_id,
                    "type": "countdown",
                    "label": label or f"Timer {new_id}",
                    "duration": seconds,
                    "start_time": datetime.now().isoformat(),
                    "end_time": end_time.isoformat(),
                    "active": True,
                }

                timers.append(timer)
                self._save_timers(timers)

                duration_str = self._format_duration(seconds)
                return (
                    f"✓ Timer started (ID: {new_id})\n"
                    f"  Label: {timer['label']}\n"
                    f"  Duration: {duration_str}\n"
                    f"  Ends at: {end_time.strftime('%H:%M:%S')}"
                )

            elif action == "pomodoro":
                # Start a Pomodoro session (25 min work + 5 min break)
                new_id = str(len(timers) + 1).zfill(4)

                # Work timer (25 minutes)
                work_end = datetime.now() + timedelta(minutes=25)
                work_timer = {
                    "id": new_id,
                    "type": "pomodoro_work",
                    "label": label or f"Pomodoro {new_id} - Work",
                    "duration": 25 * 60,
                    "start_time": datetime.now().isoformat(),
                    "end_time": work_end.isoformat(),
                    "active": True,
                }

                timers.append(work_timer)
                self._save_timers(timers)

                return (
                    f"🍅 Pomodoro started (ID: {new_id})\n"
                    f"  Label: {work_timer['label']}\n"
                    f"  Work session: 25 minutes\n"
                    f"  Ends at: {work_end.strftime('%H:%M:%S')}\n"
                    f"  After work: 5 minute break"
                )

            elif action == "list":
                if not timers:
                    return "No active timers"

                # Clean up expired timers
                now = datetime.now()
                active_timers = []
                completed_timers = []

                for timer in timers:
                    if not timer["active"]:
                        continue

                    end_time = datetime.fromisoformat(timer["end_time"])
                    if end_time <= now:
                        completed_timers.append(timer)
                        timer["active"] = False
                    else:
                        active_timers.append(timer)

                # Save updated status
                self._save_timers(timers)

                result = []
                if active_timers:
                    result.append("### Active Timers\n")
                    for timer in active_timers:
                        end_time = datetime.fromisoformat(timer["end_time"])
                        remaining = int((end_time - now).total_seconds())
                        remaining_str = self._format_duration(remaining)

                        type_icon = "🍅" if "pomodoro" in timer["type"] else "⏱️"
                        result.append(f"- [{timer['id']}] {type_icon} **{timer['label']}**")
                        result.append(f"  Remaining: {remaining_str} | Ends: {end_time.strftime('%H:%M:%S')}")

                if completed_timers:
                    result.append("\n### Completed\n")
                    for timer in completed_timers[-3:]:  # Show last 3
                        type_icon = "🍅" if "pomodoro" in timer["type"] else "✓"
                        result.append(f"- {type_icon} {timer['label']}")

                return "\n".join(result) if result else "No active timers"

            elif action == "stop":
                if not timer_id:
                    return "Error: Timer ID is required for stop action"

                stopped = False
                for timer in timers:
                    if timer["id"] == timer_id and timer["active"]:
                        timer["active"] = False
                        stopped = True
                        break

                if not stopped:
                    return f"Error: Active timer {timer_id} not found"

                self._save_timers(timers)
                return f"✓ Timer {timer_id} stopped"

            else:
                return f"Error: Unknown action '{action}'"

        except Exception as e:
            return f"Error: {e}"

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds.

        Args:
            duration_str: Duration string (e.g., '25m', '1h30m', '90s')

        Returns:
            Duration in seconds
        """
        total_seconds = 0

        # Match patterns like 1h, 30m, 90s
        pattern = r'(\d+)\s*([hms])'
        matches = re.findall(pattern, duration_str.lower())

        if not matches:
            # Try parsing as plain seconds
            try:
                return int(duration_str)
            except ValueError:
                return 0

        for value, unit in matches:
            value = int(value)
            if unit == 'h':
                total_seconds += value * 3600
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 's':
                total_seconds += value

        return total_seconds

    def _format_duration(self, seconds: int) -> str:
        """Format seconds to human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s" if secs else f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"

    def _load_timers(self) -> list[dict]:
        """Load timers from file."""
        if not self.timers_file.exists():
            return []

        try:
            with open(self.timers_file) as f:
                return json.load(f)
        except Exception:
            return []

    def _save_timers(self, timers: list[dict]):
        """Save timers to file."""
        with open(self.timers_file, "w") as f:
            json.dump(timers, f, indent=2)


# Auto-register
tool_registry.register(TimerTool())
