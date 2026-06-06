"""Memory system - persistent cross-session knowledge storage."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class Memory:
    """Manages persistent memories across sessions.

    Memories are stored as individual markdown files with YAML frontmatter
    in the memory directory. An index file (MEMORY.md) provides quick lookup.
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or Path.home() / ".terry" / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "MEMORY.md"
        self.memories: dict[str, dict[str, Any]] = {}
        self._load_memories()

    def _load_memories(self) -> None:
        """Load all memories from disk."""
        if not self.index_file.exists():
            return

        try:
            content = self.index_file.read_text(encoding="utf-8")
            for line in content.strip().split("\n"):
                if line.startswith("- ["):
                    # Parse: - [name](file.md) - description
                    parts = line.split("](", 1)
                    if len(parts) == 2:
                        name = parts[0][3:]  # Remove "- ["
                        rest = parts[1]
                        file_and_desc = rest.split(")", 1)
                        if len(file_and_desc) == 2:
                            filename = file_and_desc[0]
                            desc = file_and_desc[1].lstrip(" - ")

                            # Load full memory file
                            memory_path = self.memory_dir / filename
                            if memory_path.exists():
                                memory_content = memory_path.read_text(encoding="utf-8")
                                self.memories[name] = {
                                    "name": name,
                                    "file": filename,
                                    "description": desc,
                                    "content": memory_content,
                                }
        except Exception:
            pass

    def _save_index(self) -> None:
        """Save the memory index file."""
        lines = []
        for name, memory in self.memories.items():
            lines.append(f"- [{name}]({memory['file']}) - {memory['description']}")

        self.index_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def add(self, name: str, content: str, memory_type: str = "note",
            description: str = "") -> str:
        """Add a new memory.

        Args:
            name: Memory name (will be sanitized)
            content: Memory content (markdown)
            memory_type: Type of memory (note, decision, lesson, etc.)
            description: Short description for index

        Returns:
            Filename of the saved memory
        """
        # Sanitize name
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
        filename = f"{safe_name}.md"

        # Create frontmatter (escape YAML values to prevent injection)
        import yaml as _yaml_mod
        escaped_name = _yaml_mod.safe_dump(name).strip().rstrip(".")
        escaped_type = _yaml_mod.safe_dump(memory_type).strip().rstrip(".")
        escaped_desc = _yaml_mod.safe_dump(description or content[:100]).strip().rstrip(".")
        timestamp = datetime.now().isoformat()
        memory_content = f"""---
name: {escaped_name}
type: {escaped_type}
created: {timestamp}
description: {escaped_desc}
---

{content}
"""

        # Save memory file
        memory_path = self.memory_dir / filename
        memory_path.write_text(memory_content, encoding="utf-8")

        # Update in-memory store
        self.memories[name] = {
            "name": name,
            "file": filename,
            "description": description or content[:100],
            "content": memory_content,
        }

        # Update index
        self._save_index()

        return filename

    def get(self, name: str) -> str | None:
        """Get memory content by name.

        Args:
            name: Memory name

        Returns:
            Memory content or None if not found
        """
        memory = self.memories.get(name)
        return memory["content"] if memory else None

    def list_memories(self) -> list[dict[str, str]]:
        """List all memories.

        Returns:
            List of memory metadata (name, description, type)
        """
        result = []
        for name, memory in self.memories.items():
            result.append({
                "name": name,
                "description": memory["description"],
                "file": memory["file"],
            })
        return result

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search memories by keyword.

        Args:
            query: Search query

        Returns:
            List of matching memories
        """
        query_lower = query.lower()
        results = []

        for name, memory in self.memories.items():
            # Search in name, description, and content
            searchable = f"{name} {memory['description']} {memory['content']}".lower()
            if query_lower in searchable:
                results.append(memory)

        return results

    def delete(self, name: str) -> bool:
        """Delete a memory.

        Args:
            name: Memory name

        Returns:
            True if deleted, False if not found
        """
        memory = self.memories.get(name)
        if not memory:
            return False

        # Delete file
        memory_path = self.memory_dir / memory["file"]
        if memory_path.exists():
            memory_path.unlink()

        # Remove from store
        del self.memories[name]

        # Update index
        self._save_index()

        return True

    def update(self, name: str, content: str) -> bool:
        """Update an existing memory.

        Args:
            name: Memory name
            content: New content

        Returns:
            True if updated, False if not found
        """
        memory = self.memories.get(name)
        if not memory:
            return False

        # Preserve frontmatter
        old_content = memory["content"]
        if old_content.startswith("---"):
            # Extract existing frontmatter
            end = old_content.find("---", 3)
            if end != -1:
                frontmatter = old_content[:end + 3]
                memory_content = f"{frontmatter}\n\n{content}"
            else:
                memory_content = content
        else:
            memory_content = content

        # Save updated content
        memory_path = self.memory_dir / memory["file"]
        memory_path.write_text(memory_content, encoding="utf-8")

        # Update store
        self.memories[name]["content"] = memory_content

        return True


# Global memory instance
_memory_instance: Memory | None = None


def get_memory(memory_dir: Path | None = None) -> Memory:
    """Get or create the global memory instance.

    Args:
        memory_dir: Optional memory directory override

    Returns:
        Memory instance
    """
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = Memory(memory_dir)
    return _memory_instance


def set_memory(instance: Memory) -> None:
    """Inject a custom Memory instance (for testing/DI)."""
    global _memory_instance
    _memory_instance = instance


def reset_memory() -> None:
    """Reset memory singleton (forces re-initialization on next get)."""
    global _memory_instance
    _memory_instance = None
