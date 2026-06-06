"""Git merge tool — merge branches with --no-ff for feature branch workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitMergeTool(BaseTool):
    """Merge a branch into the current branch."""

    name = "git_merge"
    description = (
        "Merge a source branch into the current branch. "
        "Uses --no-ff by default to preserve feature branch history. "
        "Aborts on merge conflicts."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "source_branch": {
                "type": "string",
                "description": "Name of the branch to merge into current branch",
            },
            "no_ff": {
                "type": "boolean",
                "description": "Use --no-ff merge (default: true for feature branches)",
            },
            "message": {
                "type": "string",
                "description": "Optional merge commit message",
            },
        },
        "required": ["source_branch"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, source_branch: str, no_ff: bool = True, message: str = "") -> str:
        """Execute git merge."""
        try:
            # Verify source branch exists
            check = subprocess.run(
                ["git", "rev-parse", "--verify", source_branch],
                cwd=self.workdir, capture_output=True, text=True, timeout=5,
            )
            if check.returncode != 0:
                return f"Error: branch '{source_branch}' does not exist"

            cmd = ["git", "merge"]
            if no_ff:
                cmd.append("--no-ff")
            if message:
                cmd.extend(["-m", message])
            else:
                cmd.extend(["-m", f"Merge branch '{source_branch}'"])
            cmd.append(source_branch)

            result = subprocess.run(
                cmd, cwd=self.workdir, capture_output=True, text=True, timeout=30,
            )

            if result.returncode != 0:
                # Auto-abort on failure
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=self.workdir, capture_output=True, timeout=10,
                )
                return f"Merge conflict — aborted. Error: {result.stderr.strip()}"

            return result.stdout.strip() or f"Merged '{source_branch}' successfully"

        except Exception as e:
            return f"Error: {e}"


tool_registry.register(GitMergeTool())
