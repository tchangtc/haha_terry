"""Git commit tool - create commits with automated messages."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .. import BaseTool, tool_registry


class GitCommitTool(BaseTool):
    """Create git commits with descriptive messages."""

    name = "git_commit"
    description = (
        "Stage and commit changes to the git repository. "
        "Use a descriptive message following conventional commit format. "
        "Files must already exist — use write_file or edit_file to create/modify them."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Commit message (use conventional commit format: feat:, fix:, chore:, etc.)",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific files to stage (default: stage all modified/added files)",
            },
            "amend": {
                "type": "boolean",
                "description": "Amend the previous commit instead of creating a new one",
            },
        },
        "required": ["message"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        message: str,
        files: list[str] | None = None,
        amend: bool = False,
    ) -> str:
        """Stage and commit changes."""
        try:
            # Safety: reject empty or trivial messages
            if len(message.strip()) < 3:
                return "Error: commit message is too short"

            # Stage files
            if files:
                add_cmd = ["git", "add"] + files
                add_result = subprocess.run(
                    add_cmd,
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    encoding="utf-8",
                    errors="replace",
                )
                if add_result.returncode != 0:
                    return f"Error staging files: {add_result.stderr.strip()}"
            else:
                # Stage only tracked modified files (not untracked)
                add_result = subprocess.run(
                    ["git", "add", "-u"],
                    cwd=self.workdir,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    encoding="utf-8",
                    errors="replace",
                )

            # Commit
            commit_cmd = ["git", "commit"]
            if amend:
                commit_cmd.append("--amend")
                commit_cmd.extend(["--no-edit"])  # Keep original message if --amend without new message
                # But we have a new message, so:
                commit_cmd.pop()  # Remove --no-edit
                commit_cmd.extend(["-m", message])
            else:
                commit_cmd.extend(["-m", message])

            result = subprocess.run(
                commit_cmd,
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )

            output = (result.stdout + result.stderr).strip()

            if result.returncode != 0:
                if "nothing to commit" in output.lower():
                    return "(nothing to commit, working tree clean)"
                return f"Error: {output}"

            return output if output else "Commit created successfully"

        except subprocess.TimeoutExpired:
            return "Error: git commit timed out"
        except FileNotFoundError:
            return "Error: git not found. Is git installed?"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GitCommitTool())
