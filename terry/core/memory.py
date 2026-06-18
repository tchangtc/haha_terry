"""Memory system - persistent cross-session knowledge storage with typed memories and cross-references."""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml as _yaml_mod

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)


class MemoryType(StrEnum):
    """Types of persistent memories."""
    USER = "user"           # User preferences, identity, expertise
    FEEDBACK = "feedback"   # User feedback on agent behavior
    PROJECT = "project"     # Project context, goals, constraints
    REFERENCE = "reference" # External resources (URLs, docs, tickets)
    NOTE = "note"           # General notes
    SESSION_COMPACT = "session_compact"  # Auto-saved context from compaction


class Memory:
    """Manages persistent typed memories with cross-references across sessions.

    Memories are stored as individual markdown files with YAML frontmatter
    in the memory directory. An index file (MEMORY.md) provides quick lookup.
    Cross-references use [[wiki-link]] syntax within memory content.
    """

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or get_terry_dir("memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "MEMORY.md"
        self.memories: dict[str, dict[str, Any]] = {}
        self._ref_graph: dict[str, set[str]] = {}  # name → set of referenced names
        self._backlinks: dict[str, set[str]] = {}  # name → set of names that reference it
        self._load_memories()

    def _load_memories(self) -> None:
        """Load all memories from disk and rebuild reference graph."""
        self.memories.clear()
        self._ref_graph.clear()
        self._backlinks.clear()

        if not self.index_file.exists():
            return

        try:
            content = self.index_file.read_text(encoding="utf-8")
            for line in content.strip().split("\n"):
                if line.startswith("- ["):
                    parts = line.split("](", 1)
                    if len(parts) == 2:
                        name = parts[0][3:]  # Remove "- ["
                        rest = parts[1]
                        file_and_desc = rest.split(")", 1)
                        if len(file_and_desc) == 2:
                            filename = file_and_desc[0]
                            desc = file_and_desc[1].lstrip(" - ")

                            memory_path = self.memory_dir / filename
                            if memory_path.exists():
                                memory_content = memory_path.read_text(encoding="utf-8")
                                # Parse frontmatter for metadata
                                metadata = self._parse_frontmatter(memory_content)
                                self.memories[name] = {
                                    "name": name,
                                    "file": filename,
                                    "description": desc,
                                    "content": memory_content,
                                    "type": metadata.get("type", "note"),
                                    "tags": metadata.get("tags", []),
                                    "references": metadata.get("references", []),
                                    "created": metadata.get("created", ""),
                                }
        except Exception:
            logger.warning("Failed to load memories from index", exc_info=True)

        # Rebuild reference graph
        for name, memory in self.memories.items():
            refs = self._extract_references(memory.get("content", ""))
            self._ref_graph[name] = refs
            for ref in refs:
                if ref not in self._backlinks:
                    self._backlinks[ref] = set()
                self._backlinks[ref].add(name)

    def _parse_frontmatter(self, content: str) -> dict[str, Any]:
        """Parse YAML frontmatter from memory content."""
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        try:
            fm = _yaml_mod.safe_load(parts[1])
            return fm if isinstance(fm, dict) else {}
        except Exception:
            logger.warning("Failed to parse YAML frontmatter", exc_info=True)
            return {}

    def _extract_references(self, content: str) -> set[str]:
        """Extract [[wiki-link]] references from content."""
        return set(re.findall(r"\[\[([^\]]+)\]\]", content))

    def _save_index(self) -> None:
        """Save the memory index file."""
        lines = []
        for name, memory in self.memories.items():
            lines.append(f"- [{name}]({memory['file']}) - {memory['description']}")
        self.index_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def add(
        self,
        name: str,
        content: str,
        memory_type: MemoryType | str = MemoryType.NOTE,
        description: str = "",
        tags: list[str] | None = None,
        references: list[str] | None = None,
    ) -> str:
        """Add a new typed memory with optional cross-references.

        Args:
            name: Memory name (sanitized for filename)
            content: Memory content (markdown with optional [[references]])
            memory_type: Type of memory (user/feedback/project/reference/note)
            description: Short description for index
            tags: Optional tags for categorization
            references: Optional explicit [[name]] references

        Returns:
            Filename of the saved memory
        """
        type_str = memory_type.value if isinstance(memory_type, MemoryType) else memory_type
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
        filename = f"{safe_name}.md"

        # Collect references from both explicit list and [[wikilinks]] in content
        all_refs = set(references or [])
        all_refs.update(self._extract_references(content))

        tags = tags or []

        # Build frontmatter with safe YAML values
        memory_content = (
            f"---\n"
            f"name: {_yaml_mod.safe_dump(name).strip().rstrip('.')}\n"
            f"type: {_yaml_mod.safe_dump(type_str).strip().rstrip('.')}\n"
            f"created: {datetime.now().isoformat()}\n"
            f"description: {_yaml_mod.safe_dump(description or content[:100]).strip().rstrip('.')}\n"
            f"tags: {_yaml_mod.safe_dump(tags).strip()}\n"
            f"references: {_yaml_mod.safe_dump(list(all_refs)).strip()}\n"
            f"---\n\n"
            f"{content}"
        )

        # Save memory file
        memory_path = self.memory_dir / filename
        memory_path.write_text(memory_content, encoding="utf-8")

        # Update in-memory store
        self.memories[name] = {
            "name": name,
            "file": filename,
            "description": description or content[:100],
            "content": memory_content,
            "type": type_str,
            "tags": tags,
            "references": list(all_refs),
            "created": datetime.now().isoformat(),
        }

        # Update reference graph
        self._ref_graph[name] = all_refs
        for ref in all_refs:
            if ref not in self._backlinks:
                self._backlinks[ref] = set()
            self._backlinks[ref].add(name)

        # Save index
        self._save_index()

        return filename

    def add_reference(self, from_name: str, to_name: str) -> bool:
        """Create a bidirectional cross-reference between two memories.

        Args:
            from_name: Source memory name
            to_name: Target memory name

        Returns:
            True if both memories exist and reference was added
        """
        if from_name not in self.memories or to_name not in self.memories:
            return False

        # Update reference graph
        if from_name not in self._ref_graph:
            self._ref_graph[from_name] = set()
        self._ref_graph[from_name].add(to_name)

        if to_name not in self._backlinks:
            self._backlinks[to_name] = set()
        self._backlinks[to_name].add(from_name)

        # Update the source memory file to include the reference
        memory = self.memories[from_name]
        content = memory["content"]
        ref_str = f"[[{to_name}]]"

        # Only add if not already present
        if ref_str not in content:
            new_content = content.rstrip() + f"\n\nSee also: {ref_str}\n"
            memory_path = self.memory_dir / memory["file"]
            memory_path.write_text(new_content, encoding="utf-8")
            memory["content"] = new_content

        # Update frontmatter references
        existing_refs = set(memory.get("references", []))
        existing_refs.add(to_name)
        memory["references"] = list(existing_refs)

        return True

    def get_related(self, name: str, depth: int = 1) -> list[dict[str, Any]]:
        """Get memories related to the given memory via cross-references.

        Args:
            name: Memory name
            depth: BFS depth (1 = direct references, 2 = references of references)

        Returns:
            List of related memory metadata
        """
        if name not in self.memories:
            return []

        visited = {name}
        frontier = set(self._ref_graph.get(name, set()))
        frontier.update(self._backlinks.get(name, set()))
        results = []

        for _ in range(depth):
            next_frontier = set()
            for ref_name in frontier:
                if ref_name in visited:
                    continue
                visited.add(ref_name)
                if ref_name in self.memories:
                    results.append({
                        "name": ref_name,
                        "description": self.memories[ref_name]["description"],
                        "type": self.memories[ref_name].get("type", "note"),
                    })
                next_frontier.update(self._ref_graph.get(ref_name, set()))
                next_frontier.update(self._backlinks.get(ref_name, set()))
            frontier = next_frontier

        return results

    def get_by_type(self, memory_type: MemoryType | str) -> list[dict[str, Any]]:
        """Get all memories of a specific type.

        Args:
            memory_type: Type to filter by

        Returns:
            List of memory metadata
        """
        type_str = memory_type.value if isinstance(memory_type, MemoryType) else memory_type
        return [
            {
                "name": name,
                "description": mem["description"],
                "file": mem["file"],
                "tags": mem.get("tags", []),
            }
            for name, mem in self.memories.items()
            if mem.get("type") == type_str
        ]

    def get(self, name: str) -> str | None:
        """Get memory content by name."""
        memory = self.memories.get(name)
        return memory["content"] if memory else None

    def list_memories(self) -> list[dict[str, Any]]:
        """List all memories with metadata."""
        return [
            {
                "name": name,
                "description": mem["description"],
                "file": mem["file"],
                "type": mem.get("type", "note"),
                "tags": mem.get("tags", []),
            }
            for name, mem in self.memories.items()
        ]

    def list_by_recency(self, limit: int = 20) -> list[dict[str, Any]]:
        """List memories by creation time, newest first."""
        sorted_memories = sorted(
            self.memories.items(),
            key=lambda x: x[1].get("created", ""),
            reverse=True,
        )
        return [
            {
                "name": name,
                "description": mem["description"],
                "type": mem.get("type", "note"),
                "created": mem.get("created", ""),
            }
            for name, mem in sorted_memories[:limit]
        ]

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search memories by keyword in name, description, content, and tags."""
        query_lower = query.lower()
        results = []
        for name, memory in self.memories.items():
            searchable = (
                f"{name} {memory['description']} {memory['content']} "
                f"{' '.join(memory.get('tags', []))}"
            ).lower()
            if query_lower in searchable:
                results.append({
                    "name": name,
                    "description": memory["description"],
                    "type": memory.get("type", "note"),
                    "file": memory["file"],
                })
        return results

    def vector_search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Semantic search via vector embeddings (falls back to keyword if no embedder)."""
        return _vector_search_impl(self.memories, query, top_k)

    def hybrid_search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Combine keyword + vector search with Reciprocal Rank Fusion."""
        keyword_results = self.search(query)
        vector_results = self.vector_search(query, top_k * 2)
        if not vector_results or all(r.get("score", 0) == 0 for r in vector_results):
            return keyword_results[:top_k]
        scores: dict[str, float] = {}
        for rank, r in enumerate(keyword_results):
            scores[r["name"]] = scores.get(r["name"], 0) + 1.0 / (rank + 60)
        for rank, r in enumerate(vector_results):
            scores[r["name"]] = scores.get(r["name"], 0) + 1.0 / (rank + 60)
        seen: set[str] = set()
        merged = []
        for name, _ in sorted(scores.items(), key=lambda x: -x[1]):
            if name in seen:
                continue
            seen.add(name)
            mem = self.memories.get(name)
            if mem:
                merged.append({
                    "name": name,
                    "description": mem.get("description", ""),
                    "type": mem.get("type", "note"),
                    "file": mem.get("file", ""),
                    "score": round(scores[name], 4),
                })
        return merged[:top_k]

    def get_tags(self) -> list[dict[str, int]]:
        """Get all tags with usage counts, sorted by frequency."""
        tag_counts: dict[str, int] = {}
        for memory in self.memories.values():
            for tag in memory.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return sorted(
            [{"tag": tag, "count": count} for tag, count in tag_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

    def update(self, name: str, content: str) -> bool:
        """Update an existing memory's content, preserving frontmatter."""
        memory = self.memories.get(name)
        if not memory:
            return False

        old_content = memory["content"]
        if old_content.startswith("---"):
            end = old_content.find("---", 3)
            if end != -1:
                frontmatter = old_content[:end + 3]
                memory_content = f"{frontmatter}\n\n{content}"
            else:
                memory_content = content
        else:
            memory_content = content

        memory_path = self.memory_dir / memory["file"]
        memory_path.write_text(memory_content, encoding="utf-8")

        memory["content"] = memory_content
        # Update references from new content
        self._ref_graph[name] = self._extract_references(content)

        return True

    def delete(self, name: str) -> bool:
        """Delete a memory and clean up references."""
        memory = self.memories.get(name)
        if not memory:
            return False

        memory_path = self.memory_dir / memory["file"]
        if memory_path.exists():
            memory_path.unlink()

        del self.memories[name]

        # Clean up reference graph
        self._ref_graph.pop(name, None)
        self._backlinks.pop(name, None)
        for backlinks in self._backlinks.values():
            backlinks.discard(name)

        self._save_index()
        return True


# Global memory instance
_memory_instance: Memory | None = None
_memory_lock = threading.Lock()


def get_memory(memory_dir: Path | None = None) -> Memory:
    """Get or create the global memory instance."""
    global _memory_instance
    with _memory_lock:
        if _memory_instance is None:
            _memory_instance = Memory(memory_dir)
        return _memory_instance


def set_memory(instance: Memory) -> None:
    """Inject a custom Memory instance (for testing/DI)."""
    global _memory_instance
    with _memory_lock:
        _memory_instance = instance


def reset_memory() -> None:
    """Reset memory singleton."""
    global _memory_instance
    with _memory_lock:
        _memory_instance = None


def _vector_search_impl(memories: dict, query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Vector search implementation using LocalEmbedder."""
    try:
        from .local_embed import LocalEmbedder
        embedder = LocalEmbedder()
        query_vec = embedder.embed(query)
        scores = []
        for name, mem in memories.items():
            doc = f"{mem.get('description', '')} {mem.get('content', '')}"
            doc_vec = embedder.embed(doc[:500])
            sim = _cosine_sim(query_vec, doc_vec)
            if sim > 0.1:
                scores.append((name, sim, mem))
        scores.sort(key=lambda x: -x[1])
        return [
            {
                "name": n,
                "description": m.get("description", ""),
                "type": m.get("type", "note"),
                "file": m.get("file", ""),
                "score": round(s, 4),
            }
            for n, s, m in scores[:top_k]
        ]
    except (ImportError, OSError, RuntimeError):
        return []

def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
