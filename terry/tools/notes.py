"""Notes tool - quick note-taking and management."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..core.platform_utils import get_terry_dir
from . import BaseTool, tool_registry


class NotesTool(BaseTool):
    """Manage quick notes and memos."""

    name = "notes"
    description = "Create, list, search, and manage quick notes. Supports tags and categories."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "delete", "search", "show"],
                "description": "Action to perform",
            },
            "title": {
                "type": "string",
                "description": "Note title (for add action)",
            },
            "content": {
                "type": "string",
                "description": "Note content (for add action)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags for the note",
            },
            "note_id": {
                "type": "string",
                "description": "Note ID (for delete/show actions)",
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action)",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.notes_file = get_terry_dir() / "notes.json"
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        action: str,
        title: str = "",
        content: str = "",
        tags: list[str] | None = None,
        note_id: str = "",
        query: str = "",
    ) -> str:
        """Execute notes action.

        Args:
            action: Action to perform (add, list, delete, search, show)
            title: Note title (for add)
            content: Note content (for add)
            tags: Optional tags (for add)
            note_id: Note ID (for delete/show)
            query: Search query (for search)

        Returns:
            Result message
        """
        try:
            notes = self._load_notes()

            if action == "add":
                if not title or not content:
                    return "Error: Title and content are required for add action"

                # Create note
                new_id = str(len(notes) + 1).zfill(4)
                note = {
                    "id": new_id,
                    "title": title,
                    "content": content,
                    "tags": tags or [],
                    "created": datetime.now().isoformat(),
                    "modified": datetime.now().isoformat(),
                }

                notes.append(note)
                self._save_notes(notes)

                tags_str = f" [{', '.join(tags)}]" if tags else ""
                return f"✓ Note added (ID: {new_id}){tags_str}\n  Title: {title}\n  Length: {len(content)} chars"

            elif action == "list":
                if not notes:
                    return "No notes found"

                result = ["### Your Notes\n"]
                for note in sorted(notes, key=lambda x: x["modified"], reverse=True):
                    tags_str = f" [{', '.join(note['tags'])}]" if note.get("tags") else ""
                    date_str = datetime.fromisoformat(note["modified"]).strftime("%Y-%m-%d %H:%M")
                    result.append(f"- [{note['id']}] **{note['title']}**{tags_str}")
                    result.append(f"  Modified: {date_str} | {len(note['content'])} chars")

                return "\n".join(result)

            elif action == "show":
                if not note_id:
                    return "Error: Note ID is required for show action"

                for note in notes:
                    if note["id"] == note_id:
                        tags_str = f"\nTags: {', '.join(note['tags'])}" if note.get("tags") else ""
                        return (
                            f"### {note['title']}\n\n"
                            f"ID: {note['id']} | Created: {datetime.fromisoformat(note['created']).strftime('%Y-%m-%d %H:%M')}\n"
                            f"{tags_str}\n\n"
                            f"---\n\n"
                            f"{note['content']}"
                        )

                return f"Error: Note {note_id} not found"

            elif action == "delete":
                if not note_id:
                    return "Error: Note ID is required for delete action"

                original_count = len(notes)
                notes = [n for n in notes if n["id"] != note_id]

                if len(notes) == original_count:
                    return f"Error: Note {note_id} not found"

                self._save_notes(notes)
                return f"✓ Note {note_id} deleted"

            elif action == "search":
                if not query:
                    return "Error: Search query is required"

                query_lower = query.lower()
                matches = []

                for note in notes:
                    if (query_lower in note["title"].lower() or
                        query_lower in note["content"].lower() or
                        any(query_lower in tag.lower() for tag in note.get("tags", []))):
                        matches.append(note)

                if not matches:
                    return f"No notes found matching '{query}'"

                result = [f"### Search Results for '{query}'\n"]
                for note in matches:
                    tags_str = f" [{', '.join(note['tags'])}]" if note.get("tags") else ""
                    result.append(f"- [{note['id']}] **{note['title']}**{tags_str}")
                    # Show snippet
                    snippet = note["content"][:100].replace("\n", " ")
                    result.append(f"  {snippet}...")

                return "\n".join(result)

            else:
                return f"Error: Unknown action '{action}'"

        except Exception as e:
            return f"Error: {e}"

    def _load_notes(self) -> list[dict]:
        """Load notes from file."""
        if not self.notes_file.exists():
            return []

        try:
            with open(self.notes_file) as f:
                return json.load(f)
        except Exception:
            return []

    def _save_notes(self, notes: list[dict]):
        """Save notes to file."""
        with open(self.notes_file, "w") as f:
            json.dump(notes, f, indent=2)


# Auto-register
tool_registry.register(NotesTool())
