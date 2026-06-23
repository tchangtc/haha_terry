"""Git diff tool - show working tree changes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitDiffTool(BaseTool):
    """Show git diff between working tree, index, or commits."""
    risk_level = "read_only"
    category = "git"

    name = "git_diff"
    description = (
        "Show git diff for staged changes, unstaged changes, or between commits. "
        "Use pathspec to filter by path."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pathspec": {
                "type": "string",
                "description": "Optional path filter (e.g., 'src/models.py')",
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged changes (--cached)",
            },
            "base": {
                "type": "string",
                "description": "Base ref to compare from (default: HEAD)",
            },
            "target": {
                "type": "string",
                "description": "Target ref to compare to (optional, for comparing two commits)",
            },
        },
        "required": [],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        pathspec: str | None = None,
        staged: bool = False,
        base: str = "HEAD",
        target: str | None = None,
    ) -> str:
        """Show git diff."""
        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--staged")

            if target:
                cmd.extend([f"{base}..{target}"])
            elif base and base != "HEAD":
                cmd.append(base)

            if pathspec:
                cmd.extend(["--", pathspec])

            result = subprocess.run(
                cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stdout + result.stderr).strip()

            # Truncate large diffs
            if len(output) > 50000:
                output = output[:50000] + (
                    f"\n\n... (diff truncated, {len(output) - 50000} chars omitted. "
                    "Use pathspec to narrow down.)"
                )

            return output if output else "(no changes)"

        except subprocess.TimeoutExpired:
            return "Error: git diff timed out after 30 seconds"
        except FileNotFoundError:
            return "Error: git not found. Is git installed?"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GitDiffTool())
