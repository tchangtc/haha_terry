"""Jupyter notebook (.ipynb) editing tool."""

from __future__ import annotations

import json
from pathlib import Path

from . import BaseTool, tool_registry


class NotebookEditTool(BaseTool):
    """Edit Jupyter notebook cells with replace, insert, or delete operations."""
    risk_level = "destructive"
    category = "file"

    name = "notebook_edit"
    description = (
        "Edit a Jupyter notebook (.ipynb) by replacing, inserting, or deleting cells. "
        "Use 'replace' to update a cell's source, 'insert' to add a new cell, "
        "or 'delete' to remove a cell."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the .ipynb file",
            },
            "edit_mode": {
                "type": "string",
                "enum": ["replace", "insert", "delete"],
                "description": "Edit operation: replace cell, insert new cell, or delete cell",
            },
            "cell_index": {
                "type": "integer",
                "description": "Cell index (0-based). For insert, new cell goes after this index.",
            },
            "new_source": {
                "type": "string",
                "description": "New source code (for replace/insert modes)",
            },
            "cell_type": {
                "type": "string",
                "enum": ["code", "markdown"],
                "description": "Cell type (for insert mode, defaults to 'code')",
            },
        },
        "required": ["path", "edit_mode"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    def execute(
        self,
        path: str,
        edit_mode: str = "replace",
        cell_index: int | None = None,
        new_source: str | None = None,
        cell_type: str = "code",
    ) -> str:
        """Edit a Jupyter notebook."""
        try:
            file_path = (self.workdir / path).resolve()
            if not file_path.is_relative_to(self.workdir.resolve()):
                return f"Error: Path escapes workspace: {path}"

            if not file_path.exists():
                return f"Error: File not found: {path}"

            if not file_path.suffix == ".ipynb":
                return "Error: File must have .ipynb extension"

            # Load notebook
            nb = json.loads(file_path.read_text(encoding="utf-8"))
            cells = nb.get("cells", [])

            if edit_mode == "replace":
                if cell_index is None or new_source is None:
                    return "Error: 'replace' mode requires cell_index and new_source"
                if cell_index < 0 or cell_index >= len(cells):
                    return f"Error: cell_index {cell_index} out of range (0-{len(cells)-1})"
                old_source = cells[cell_index].get("source", "")
                cells[cell_index]["source"] = (
                    new_source.split("\n") if isinstance(old_source, list)
                    else new_source
                )
                summary = f"Replaced cell {cell_index} in {path}\nNew source:\n```\n{new_source[:500]}\n```"

            elif edit_mode == "insert":
                if new_source is None:
                    return "Error: 'insert' mode requires new_source"
                new_cell = {
                    "cell_type": cell_type,
                    "metadata": {},
                    "source": new_source.split("\n") if cell_type == "code" else new_source,
                    "outputs": [] if cell_type == "code" else None,
                    "execution_count": None,
                }
                if cell_index is not None and cell_index < len(cells):
                    cells.insert(cell_index + 1, new_cell)
                else:
                    cells.append(new_cell)
                summary = f"Inserted new {cell_type} cell at position {cell_index + 1 if cell_index is not None else len(cells)}"

            elif edit_mode == "delete":
                if cell_index is None:
                    return "Error: 'delete' mode requires cell_index"
                if cell_index < 0 or cell_index >= len(cells):
                    return f"Error: cell_index {cell_index} out of range (0-{len(cells)-1})"
                deleted = cells.pop(cell_index)
                deleted_preview = str(deleted.get("source", ""))[:200]
                summary = f"Deleted cell {cell_index}: {deleted_preview}..."

            else:
                return f"Error: Unknown edit_mode '{edit_mode}'"

            # Persist the mutation to disk (previously unreachable — every branch
            # returned before this block ran, so edits were silently dropped).
            nb["cells"] = cells
            file_path.write_text(
                json.dumps(nb, indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
            return summary

        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in notebook: {e}"
        except Exception as e:
            return f"Error: {e}"


# Auto-register
tool_registry.register(NotebookEditTool())
