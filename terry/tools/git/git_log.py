"""Git log tool - view commit history."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitLogTool(BaseTool):
    """View git commit history."""

    name = "git_log"
    description = (
        "Show git commit history. Supports limiting by count, filtering by file, "
        "and various output formats. Use this before git_diff to understand the "
        "project's recent history."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "Number of recent commits to show (default: 10)",
            },
            "pathspec": {
                "type": "string",
                "description": "Filter commits affecting this file/directory",
            },
            "oneline": {
                "type": "boolean",
                "description": "Show one-line format (default: true)",
            },
            "author": {
                "type": "string",
                "description": "Filter by author name/email",
            },
            "since": {
                "type": "string",
                "description": "Show commits since date (e.g., '2026-01-01', '2 weeks ago')",
            },
        },
        "required": [],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        count: int | None = 10,
        pathspec: str | None = None,
        oneline: bool = True,
        author: str | None = None,
        since: str | None = None,
    ) -> str:
        """Show git log."""
        try:
            cmd = ["git", "log"]

            if oneline:
                cmd.append("--oneline")
            else:
                cmd.extend(["--pretty=format:%h - %an, %ar : %s"])

            if count is not None and count > 0:
                cmd.extend(["-n", str(min(count, 100))])

            if author:
                cmd.extend(["--author", author])

            if since:
                cmd.extend(["--since", since])

            if pathspec:
                cmd.extend(["--", pathspec])

            result = subprocess.run(
                cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=15,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stdout + result.stderr).strip()

            # Truncate very long logs
            if len(output) > 30000:
                output = output[:30000] + "\n\n... (log truncated)"

            return output if output else "(no commits yet)"

        except subprocess.TimeoutExpired:
            return "Error: git log timed out"
        except FileNotFoundError:
            return "Error: git not found. Is git installed?"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GitLogTool())
