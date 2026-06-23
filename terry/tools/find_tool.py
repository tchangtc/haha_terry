"""Find tool - search for files by name or path pattern."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from . import BaseTool, tool_registry


class FindTool(BaseTool):
    """Find files by name or path pattern."""
    risk_level = "read_only"
    category = "file"

    name = "find"
    description = "Search for files by name or path pattern. Supports glob patterns and recursive search."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "File pattern to match (e.g., '*.py', 'test_*')",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory)",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively in subdirectories",
                "default": True,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 100,
            },
        },
        "required": ["pattern"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        pattern: str,
        path: str = ".",
        recursive: bool = True,
        max_results: int = 100,
    ) -> str:
        """Execute find search.

        Args:
            pattern: File pattern to match
            path: Directory to search in
            recursive: Search recursively
            max_results: Maximum results to return

        Returns:
            List of matching files
        """
        try:
            # Security: resolve path and check it's within workdir
            search_path = (self.workdir / path).resolve()
            if not search_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not search_path.exists():
                return f"Error: Path not found: {path}"

            # Find files
            matches = []

            if recursive:
                # Recursive search
                for file_path in search_path.rglob("*"):
                    if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                        # Make path relative to workdir
                        rel_path = file_path.relative_to(self.workdir)
                        matches.append(str(rel_path))

                        if len(matches) >= max_results:
                            break
            else:
                # Non-recursive search
                for file_path in search_path.glob("*"):
                    if file_path.is_file() and fnmatch.fnmatch(file_path.name, pattern):
                        # Make path relative to workdir
                        rel_path = file_path.relative_to(self.workdir)
                        matches.append(str(rel_path))

                        if len(matches) >= max_results:
                            break

            if not matches:
                return f"No files found matching pattern: {pattern}"

            # Sort results
            matches.sort()

            # Format output
            output = "\n".join(matches)
            if len(matches) >= max_results:
                output += f"\n... (showing first {max_results} results)"

            return output

        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(FindTool())
