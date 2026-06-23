"""Write file tool - create or overwrite files."""

from __future__ import annotations

from pathlib import Path

from . import BaseTool, tool_registry


class WriteFileTool(BaseTool):
    """Write content to a file (create or overwrite)."""
    risk_level = "destructive"
    category = "file"

    name = "write_file"
    description = "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, content: str) -> str:
        """Write content to file."""
        try:
            # Security: resolve path and check it's within workdir
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            file_path.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(WriteFileTool())
