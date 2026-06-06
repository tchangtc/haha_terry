"""Bash tool - cross-platform shell command execution with security controls."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.platform_utils import is_windows
from ..core.security import RequestValidator
from . import BaseTool, tool_registry


class BashTool(BaseTool):
    """Execute shell commands with security controls (cross-platform)."""

    name = "bash"
    description = "Run a shell command in the working directory (Windows: cmd.exe, Unix: sh/bash)."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            }
        },
        "required": ["command"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, command: str) -> str:
        """Execute a shell command (cross-platform)."""
        # Sanitize command to prevent dangerous patterns
        is_safe, sanitized_command, warning = RequestValidator.sanitize_bash_command(command)
        if not is_safe:
            return f"Error: {warning}"

        # Use sanitized command if available, otherwise original
        command_to_run = sanitized_command if is_safe else command

        try:
            # Platform-specific command execution
            if is_windows():
                # Windows: use cmd.exe
                result = subprocess.run(
                    ['cmd.exe', '/c', command_to_run],
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding='utf-8',
                    errors='replace',
                )
            else:
                # Unix-like: use sh -c
                shell = '/bin/sh'
                result = subprocess.run(
                    [shell, '-c', command_to_run],
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding='utf-8',
                    errors='replace',
                )

            output = (result.stdout + result.stderr).strip()

            # Limit output to prevent context overflow
            if len(output) > 50000:
                output = output[:50000] + f"\n... (truncated, {len(output) - 50000} chars omitted)"

            return output if output else "(no output)"

        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 120 seconds"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(BashTool())
