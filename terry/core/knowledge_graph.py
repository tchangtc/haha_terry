"""Knowledge graph for cross-session entity tracking.

Builds a semantic graph of entities (files, functions, errors, decisions)
extracted from conversations, enabling context retrieval across sessions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class KnowledgeGraph:
    """Lightweight in-memory knowledge graph with JSON persistence.

    Tracks entities and relationships across conversations.
    Supports graph traversal and Graphviz export.
    """

    MAX_NODES = 1000
    MAX_EDGES = 5000

    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".terry" / "knowledge_graph.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        """Load graph from disk."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
            except Exception:
                self.nodes = {}
                self.edges = []

    def _save(self) -> None:
        """Persist graph to disk."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "nodes": self.nodes,
            "edges": self.edges,
        }
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_node(self, node_id: str, node_type: str = "entity", **properties) -> bool:
        """Add or update a node."""
        if len(self.nodes) >= self.MAX_NODES:
            return False
        self.nodes[node_id] = {
            "type": node_type,
            "properties": properties,
            "added_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
        self._save()
        return True

    def add_edge(
        self, source: str, target: str, relation: str = "related_to"
    ) -> bool:
        """Add a directed edge between nodes."""
        if source not in self.nodes:
            self.add_node(source)
        if target not in self.nodes:
            self.add_node(target)

        if len(self.edges) >= self.MAX_EDGES:
            return False

        # Avoid duplicates
        existing = any(
            e["source"] == source and e["target"] == target and e["relation"] == relation
            for e in self.edges
        )
        if not existing:
            self.edges.append({
                "source": source,
                "target": target,
                "relation": relation,
            })
            self._save()
        return True

    def get_related(
        self, node_id: str, depth: int = 2, relation: str | None = None
    ) -> list[dict[str, Any]]:
        """Get nodes related to node_id up to a given depth."""
        if node_id not in self.nodes:
            return []

        visited = {node_id}
        frontier = [node_id]
        results = []

        for _ in range(depth):
            next_frontier = []
            for current in frontier:
                for edge in self.edges:
                    if relation and edge["relation"] != relation:
                        continue
                    neighbor = None
                    if edge["source"] == current and edge["target"] not in visited:
                        neighbor = edge["target"]
                    elif edge["target"] == current and edge["source"] not in visited:
                        neighbor = edge["source"]

                    if neighbor and neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
                        if neighbor in self.nodes:
                            results.append({
                                "id": neighbor,
                                "type": self.nodes[neighbor]["type"],
                                "relation": edge["relation"],
                                "properties": self.nodes[neighbor].get("properties", {}),
                            })
            frontier = next_frontier

        return results

    def search_nodes(self, query: str) -> list[dict[str, Any]]:
        """Search nodes by ID or properties."""
        q = query.lower()
        results = []
        for nid, node in self.nodes.items():
            props_str = str(node.get("properties", {})).lower()
            if q in nid.lower() or q in props_str:
                results.append({"id": nid, **node})
        return results

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its edges."""
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        self.edges = [
            e for e in self.edges
            if e["source"] != node_id and e["target"] != node_id
        ]
        self._save()
        return True

    def to_graphviz(self) -> str:
        """Export to Graphviz DOT format."""
        lines = ["digraph KnowledgeGraph {", "  rankdir=LR;"]
        for nid, node in self.nodes.items():
            label = node.get("properties", {}).get("name", nid)
            lines.append(f'  "{nid}" [label="{label}"];')
        for edge in self.edges:
            lines.append(
                f'  "{edge["source"]}" -> "{edge["target"]}" '
                f'[label="{edge["relation"]}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    def get_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_types": len(set(n.get("type", "entity") for n in self.nodes.values())),
        }
