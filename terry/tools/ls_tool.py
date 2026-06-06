"""List directory tool - list files and directories."""

from __future__ import annotations

from pathlib import Path
import os

from . import BaseTool, tool_registry


class LsTool(BaseTool):
    """List files and directories in a path."""

    name = "ls"
    description = "List files and directories. Shows file sizes, permissions, and modification times."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list (default: current directory)",
                "default": ".",
            },
            "show_all": {
                "type": "boolean",
                "description": "Show hidden files (starting with .)",
                "default": False,
            },
            "long": {
                "type": "boolean",
                "description": "Use long format with details",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        path: str = ".",
        show_all: bool = False,
        long: bool = True,
    ) -> str:
        """Execute ls command.

        Args:
            path: Directory to list
            show_all: Show hidden files
            long: Use long format

        Returns:
            Directory listing
        """
        try:
            # Security: resolve path and check it's within workdir
            list_path = (self.workdir / path).resolve()
            if not list_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not list_path.exists():
                return f"Error: Path not found: {path}"

            if not list_path.is_dir():
                return f"Error: Not a directory: {path}"

            # Get entries
            entries = []
            for entry in list_path.iterdir():
                # Skip hidden files unless requested
                if not show_all and entry.name.startswith("."):
                    continue

                if long:
                    # Long format
                    try:
                        stat = entry.stat()
                        size = self._format_size(stat.st_size)
                        mtime = self._format_time(stat.st_mtime)
                        file_type = "d" if entry.is_dir() else "-"

                        entries.append(f"{file_type} {size:>10s} {mtime} {entry.name}")
                    except Exception:
                        entries.append(f"? {entry.name}")
                else:
                    # Short format
                    entries.append(entry.name)

            if not entries:
                return "Directory is empty"

            # Sort entries (directories first, then files)
            if long:
                entries.sort(key=lambda x: (not x.startswith("d"), x))
            else:
                entries.sort()

            return "\n".join(entries)

        except Exception as e:
            return f"Error: {e}"

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format.

        Args:
            size: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"

    def _format_time(self, timestamp: float) -> str:
        """Format timestamp.

        Args:
            timestamp: Unix timestamp

        Returns:
            Formatted time string
        """
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")


# Auto-register
tool_registry.register(LsTool())
