"""Git status tool - show working tree status."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitStatusTool(BaseTool):
    """Show the working tree status."""

    name = "git_status"
    description = (
        "Show the working tree status including staged, unstaged, and untracked files. "
        "Returns output in short format for easy parsing."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "porcelain": {
                "type": "boolean",
                "description": "Use machine-readable porcelain format (default: true)",
            },
            "pathspec": {
                "type": "string",
                "description": "Optional path filter",
            },
        },
        "required": [],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        porcelain: bool = True,
        pathspec: str | None = None,
    ) -> str:
        """Show git status."""
        try:
            cmd = ["git", "status"]
            if porcelain:
                cmd.append("--porcelain")
            else:
                cmd.append("--short")
            cmd.append("--branch")

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
            return output if output else "(clean working tree)"

        except subprocess.TimeoutExpired:
            return "Error: git status timed out"
        except FileNotFoundError:
            return "Error: git not found. Is git installed?"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GitStatusTool())
