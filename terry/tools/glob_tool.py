"""Glob tool - find files by pattern."""

from __future__ import annotations

import glob
from pathlib import Path

from . import BaseTool, tool_registry


class GlobTool(BaseTool):
    """Find files matching a glob pattern."""
    risk_level = "read_only"
    category = "file"

    name = "glob"
    description = "Find files matching a glob pattern (e.g., '**/*.py', 'src/*.md')."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files (e.g., '**/*.py')",
            }
        },
        "required": ["pattern"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, pattern: str) -> str:
        """Find files matching pattern."""
        try:
            results = []
            for match in glob.glob(pattern, root_dir=self.workdir, recursive=True):
                # Security: ensure matched path is within workdir
                match_path = (self.workdir / match).resolve()
                if match_path.is_relative_to(self.workdir.resolve()):
                    results.append(match)

            if not results:
                return "(no matches)"

            # Sort and limit results
            results.sort()
            if len(results) > 100:
                return "\n".join(results[:100]) + f"\n... ({len(results) - 100} more matches)"

            return "\n".join(results)
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(GlobTool())
