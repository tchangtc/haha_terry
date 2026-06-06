"""Read file tool - read file contents with pagination."""

from __future__ import annotations

from pathlib import Path

from . import BaseTool, tool_registry


class ReadFileTool(BaseTool):
    """Read file contents with optional line limit."""

    name = "read_file"
    description = "Read the contents of a file. Use 'limit' to read only the first N lines."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (optional)",
            },
        },
        "required": ["path"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, limit: int | None = None) -> str:
        """Read file contents."""
        try:
            # Security: resolve path and check it's within workdir
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not file_path.exists():
                return f"Error: File not found: {path}"

            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if limit and limit < len(lines):
                lines = lines[:limit] + [f"\n... ({len(lines) - limit} more lines)"]

            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(ReadFileTool())
