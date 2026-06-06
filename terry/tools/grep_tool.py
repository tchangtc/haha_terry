"""Grep tool - cross-platform file content search using pure Python."""

from __future__ import annotations

import re
from pathlib import Path

from . import BaseTool, tool_registry


class GrepTool(BaseTool):
    """Search file contents using regex patterns (cross-platform, pure Python)."""

    name = "grep"
    description = "Search for text patterns in files using regex. Pure Python implementation (no external grep needed)."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text pattern to search for (supports regex)",
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in (default: current directory)",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search recursively in subdirectories",
                "default": True,
            },
            "ignore_case": {
                "type": "boolean",
                "description": "Case-insensitive search",
                "default": False,
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
        ignore_case: bool = False,
    ) -> str:
        """Search for pattern in files (pure Python implementation)."""
        try:
            # Security: resolve path and check it's within workdir
            search_path = (self.workdir / path).resolve()
            if not search_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not search_path.exists():
                return f"Error: Path not found: {path}"

            # Compile regex pattern
            flags = re.IGNORECASE if ignore_case else 0
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return f"Error: Invalid regex pattern: {e}"

            # Search files
            matches = []
            max_matches = 100

            if search_path.is_file():
                # Search single file
                file_matches = self._search_file(search_path, regex, max_matches)
                matches.extend(file_matches)
            elif search_path.is_dir():
                # Search directory
                if recursive:
                    files = search_path.rglob('*')
                else:
                    files = search_path.glob('*')

                for file_path in files:
                    if file_path.is_file() and not self._is_binary(file_path):
                        file_matches = self._search_file(
                            file_path,
                            regex,
                            max_matches - len(matches)
                        )
                        matches.extend(file_matches)

                        if len(matches) >= max_matches:
                            break

            if not matches:
                return f"No matches found for pattern: {pattern}"

            # Format output
            output_lines = []
            for file_path, line_num, line_text in matches[:max_matches]:
                # Make path relative to workdir for cleaner output
                rel_path = file_path.relative_to(self.workdir)
                output_lines.append(f"{rel_path}:{line_num}:{line_text}")

            output = "\n".join(output_lines)

            if len(matches) > max_matches:
                output += f"\n... ({len(matches) - max_matches} more matches, showing first {max_matches})"

            return output

        except Exception as e:
            return f"Error: {e}"

    def _search_file(
        self,
        file_path: Path,
        regex: re.Pattern,
        max_results: int
    ) -> list[tuple[Path, int, str]]:
        """Search a single file for pattern matches.

        Args:
            file_path: Path to file
            regex: Compiled regex pattern
            max_results: Maximum number of results to return

        Returns:
            List of (file_path, line_number, line_text) tuples
        """
        matches = []

        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        matches.append((file_path, line_num, line.rstrip()))

                        if len(matches) >= max_results:
                            break
        except OSError:
            # Skip files that can't be read
            pass

        return matches

    def _is_binary(self, file_path: Path) -> bool:
        """Check if file is likely binary.

        Args:
            file_path: Path to file

        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                # Empty file is not binary
                if not chunk:
                    return False
                # Check for null bytes (common in binary files)
                if b'\x00' in chunk:
                    return True
                # Check for high ratio of non-text bytes
                text_chars = bytes(range(32, 127)) + b'\n\r\t'
                non_text = sum(1 for byte in chunk if byte not in text_chars)
                return non_text / len(chunk) > 0.3
        except OSError:
            return True


# Auto-register
tool_registry.register(GrepTool())
