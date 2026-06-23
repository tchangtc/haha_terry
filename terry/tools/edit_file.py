"""Edit file tool - search and replace with diff preview."""

from __future__ import annotations

import difflib
from pathlib import Path

from . import BaseTool, tool_registry


class EditFileTool(BaseTool):
    """Edit file by replacing exact text matches."""
    risk_level = "destructive"
    category = "file"

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


class MultiEditTool(BaseTool):
    """Edit file at multiple locations in a single call with rollback on failure."""
    risk_level = "destructive"
    category = "file"

    name = "multi_edit"
    description = (
        "Edit a file at multiple locations in a single call. "
        "Each edit specifies old_text and new_text. "
        "All edits are applied atomically — if any edit fails (text not found or not unique), "
        "the entire operation is rolled back. "
        "Use this instead of multiple edit_file calls when you need to make several changes at once."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_text": {
                            "type": "string",
                            "description": "Exact text to find (must appear exactly once)",
                        },
                        "new_text": {
                            "type": "string",
                            "description": "Text to replace with",
                        },
                    },
                    "required": ["old_text", "new_text"],
                },
                "description": "List of edits to apply sequentially",
            },
        },
        "required": ["path", "edits"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(self, path: str, edits: list[dict]) -> str:
        """Apply multiple edits atomically."""
        try:
            # Security: resolve path and check workspace bounds
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not file_path.exists():
                return f"Error: File not found: {path}"

            if not edits:
                return "Error: edits list is empty"

            original_content = file_path.read_text(encoding="utf-8")
            current_content = original_content

            # Validate all edits first (fail-fast)
            edit_results = []
            for i, edit in enumerate(edits):
                old_text = edit.get("old_text", "")
                new_text = edit.get("new_text", "")
                count = current_content.count(old_text)
                if count == 0:
                    return (
                        f"Error: Edit {i + 1}/{len(edits)} failed — "
                        f"text not found in {path}. All edits rolled back."
                    )
                if count > 1:
                    return (
                        f"Error: Edit {i + 1}/{len(edits)} failed — "
                        f"text appears {count} times in {path}, must be unique. "
                        f"All edits rolled back."
                    )
                # Apply this edit to accumulate changes
                current_content = current_content.replace(old_text, new_text, 1)
                edit_results.append({
                    "index": i,
                    "old_text_preview": old_text[:60],
                    "new_text_preview": new_text[:60],
                    "success": True,
                })

            # Generate full diff (original → final)
            diff = "\n".join(
                difflib.unified_diff(
                    original_content.splitlines(keepends=True),
                    current_content.splitlines(keepends=True),
                    fromfile=path,
                    tofile=path,
                    lineterm="",
                )
            )

            # Write final content
            file_path.write_text(current_content, encoding="utf-8")

            # Build result summary
            summary_parts = [f"Applied {len(edits)} edit(s) to {path}:\n"]
            for r in edit_results:
                summary_parts.append(
                    f"  Edit {r['index'] + 1}: "
                    f"\"{r['old_text_preview']}{'...' if len(r.get('old_text_preview', '')) >= 60 else ''}\" "
                    f"→ \"{r['new_text_preview']}{'...' if len(r.get('new_text_preview', '')) >= 60 else ''}\""
                )
            summary_parts.append(f"\nDiff:\n{diff}")

            return "\n".join(summary_parts)

        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(EditFileTool())
tool_registry.register(MultiEditTool())
