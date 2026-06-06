"""Git branch tool — list, create, and switch branches."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitBranchTool(BaseTool):
    """List, create, and switch git branches."""

    name = "git_branch"
    description = (
        "List local branches, create a new branch with optional switch, "
        "or show the current branch. Branch names should follow the pattern "
        "feat/, fix/, chore/, test/, refactor/."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "current"],
                "description": "list=show all branches, create=make new branch, current=show current",
            },
            "name": {
                "type": "string",
                "description": "Branch name (required for create). Use conventional prefix: feat/, fix/, chore/, test/, refactor/.",
            },
            "switch": {
                "type": "boolean",
                "description": "Switch to the new branch after creation (default: true)",
            },
        },
        "required": ["action"],
    }

    VALID_PREFIXES = ("feat/", "fix/", "chore/", "test/", "refactor/", "docs/")

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, action: str, name: str = "", switch: bool = True) -> str:
        """Execute git branch operations."""
        try:
            if action == "current":
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=self.workdir, capture_output=True, text=True, timeout=5,
                )
                return result.stdout.strip() or "(not on any branch)"

            elif action == "list":
                result = subprocess.run(
                    ["git", "branch"],
                    cwd=self.workdir, capture_output=True, text=True, timeout=5,
                )
                return result.stdout.strip() or "(no branches)"

            elif action == "create":
                if not name:
                    return "Error: branch name required for create action"
                if not name.startswith(self.VALID_PREFIXES):
                    return (
                        f"Error: branch name must start with one of: "
                        f"{', '.join(self.VALID_PREFIXES)}"
                    )
                subprocess.run(
                    ["git", "checkout", "-b", name],
                    cwd=self.workdir, capture_output=True, text=True, timeout=10,
                    check=True,
                )
                return f"Created and switched to branch '{name}'"

            else:
                return f"Error: unknown action '{action}'"

        except subprocess.CalledProcessError as e:
            return f"Error: {e.stderr.strip()}"
        except Exception as e:
            return f"Error: {e}"


tool_registry.register(GitBranchTool())
