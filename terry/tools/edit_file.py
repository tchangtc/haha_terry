"""Edit file tool - search and replace with diff preview."""

from __future__ import annotations

import difflib
from pathlib import Path

from . import BaseTool, tool_registry


class EditFileTool(BaseTool):
    """Edit file by replacing exact text matches."""

    name = "edit_file"
    description = "Replace exact text in a file. The old_text must appear exactly once in the file."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_text": {
                "type": "string",
                "description": "Exact text to find (must appear exactly once)",
            },
            "new_text": {
                "type": "string",
                "description": "Text to replace with",
            },
        },
        "required": ["path", "old_text", "new_text"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, old_text: str, new_text: str) -> str:
        """Edit file by replacing text."""
        try:
            # Security: resolve path and check it's within workdir
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")

            # Validate: old_text must appear exactly once
            count = content.count(old_text)
            if count == 0:
                return f"Error: Text not found in {path}"
            if count > 1:
                return f"Error: Text appears {count} times in {path}, must be unique"

            # Perform replacement
            new_content = content.replace(old_text, new_text, 1)

            # Generate diff for preview
            diff = "\n".join(
                difflib.unified_diff(
                    content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=path,
                    tofile=path,
                    lineterm="",
                )
            )

            # Write back
            file_path.write_text(new_content, encoding="utf-8")

            return f"Edited {path}\n\nDiff:\n{diff}"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(EditFileTool())
