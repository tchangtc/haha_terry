"""Git checkout tool - switch branches or restore files."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitCheckoutTool(BaseTool):
    """Switch branches or restore files."""

    name = "git_checkout"
    description = (
        "Switch to a different branch or restore specific files from HEAD/the index. "
        "Use 'branch' to switch branches. "
        "Use 'files' to restore specific files (discards unstaged changes). "
        "Use 'create_branch' to create and switch to a new branch."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {
                "type": "string",
                "description": "Branch name to switch to",
            },
            "create_branch": {
                "type": "string",
                "description": "Create a new branch with this name and switch to it (like git checkout -b)",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to restore from HEAD (discards local changes!)",
            },
        },
        "required": [],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        branch: str | None = None,
        create_branch: str | None = None,
        files: list[str] | None = None,
    ) -> str:
        """Switch branch or restore files."""
        try:
            # Safety: disallow dangerous operations
            if branch and branch.startswith("-"):
                return "Error: invalid branch name"

            if create_branch:
                # Create and switch to new branch
                result = subprocess.run(
                    ["git", "checkout", "-b", create_branch],
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace",
                )
                output = (result.stdout + result.stderr).strip()
                if result.returncode != 0:
                    return f"Error creating branch '{create_branch}': {output}"
                return output if output else f"Switched to new branch '{create_branch}'"

            if files:
                # Restore specific files from HEAD
                restore_cmd = ["git", "restore"]
                # Warn about discarding changes
                warning = "Warning: This will discard unstaged changes in the specified files.\n"
                result = subprocess.run(
                    restore_cmd + files,
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace",
                )
                output = (result.stdout + result.stderr).strip()
                if result.returncode != 0:
                    return f"Error restoring files: {output}"
                return warning + (output if output else f"Restored {', '.join(files)} from HEAD")

            if branch:
                # Switch to existing branch
                result = subprocess.run(
                    ["git", "checkout", branch],
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace",
                )
                output = (result.stdout + result.stderr).strip()
                if result.returncode != 0:
                    return f"Error switching to '{branch}': {output}"
                return output if output else f"Switched to branch '{branch}'"

            return "Error: specify 'branch', 'create_branch', or 'files'"

        except subprocess.TimeoutExpired:
            return "Error: git checkout timed out"
        except FileNotFoundError:
            return "Error: git not found. Is git installed?"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GitCheckoutTool())
