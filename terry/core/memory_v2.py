"""Memory 2.0 — cross-project memory with preference learning.

Extends the existing Memory system with:
- Cross-project shared memory (patterns learned in one project apply to others)
- User preference learning (auto-detect user preferences from interactions)
- Project-level knowledge graph enrichment
- Memory decay and reinforcement

Usage:
    from terry.core.memory_v2 import MemoryV2
    mem = MemoryV2()
    mem.learn_preference("code_style", "prefer type hints")
    prefs = mem.get_preferences("code_style")
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────

MEMORY_DECAY_DAYS = 30        # Memories older than this are deprecated
PREFERENCE_CONFIDENCE_MIN = 3  # Minimum observations before learning a preference


@dataclass
class MemoryEntry:
    """A cross-project memory entry."""

    key: str
    value: str
    project: str = ""           # Source project, "" for global
    category: str = "general"   # code_style, tool_pref, pattern, fact
    confidence: int = 1          # Reinforcement count
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "value": self.value,
            "project": self.project, "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at, "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        return cls(**{k: data.get(k, v.default if v.default is not v.default else "")
                       for k, v in cls.__dataclass_fields__.items()})


class MemoryV2:
    """Cross-project memory with preference learning."""

    def __init__(self, storage_dir: Path | None = None):
        if storage_dir is None:
            from terry.core.platform_utils import get_terry_dir
            storage_dir = get_terry_dir() / "memory_v2"
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self):
        path = self._dir / "memory.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._entries = {
                    k: MemoryEntry.from_dict(v) for k, v in data.items()
                }
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self):
        data = {k: v.to_dict() for k, v in self._entries.items()}
        (self._dir / "memory.json").write_text(json.dumps(data, indent=2))

    # ── CRUD ──────────────────────────────────────────────────────

    def remember(self, key: str, value: str, project: str = "",
                 category: str = "general"):
        """Store or reinforce a memory."""
        if key in self._entries:
            entry = self._entries[key]
            entry.confidence += 1
            entry.last_used = time.time()
            entry.value = value  # Update with latest
        else:
            self._entries[key] = MemoryEntry(
                key=key, value=value, project=project,
                category=category, confidence=1,
            )
        self._save()

    def recall(self, key: str) -> str | None:
        """Retrieve a memory by key."""
        entry = self._entries.get(key)
        if entry:
            entry.last_used = time.time()
            self._save()
            return entry.value
        return None

    def forget(self, key: str):
        """Remove a memory."""
        self._entries.pop(key, None)
        self._save()

    # ── Preference Learning ───────────────────────────────────────

    def learn_preference(self, category: str, preference: str):
        """Record a user preference observation.

        After MIN_CONFIDENCE observations of the same preference, it becomes
        a learned preference.
        """
        key = f"pref:{category}:{preference}"
        self.remember(key, preference, category=category)

    def get_preferences(self, category: str | None = None) -> dict[str, str]:
        """Get learned preferences, optionally filtered by category."""
        prefs = {}
        for key, entry in self._entries.items():
            if not key.startswith("pref:"):
                continue
            if entry.confidence < PREFERENCE_CONFIDENCE_MIN:
                continue
            pref_category = entry.category
            if category and pref_category != category:
                continue
            pref_name = key.split(":", 2)[-1].rsplit(":", 1)[0]
            prefs[pref_name] = entry.value
        return prefs

    # ── Querying ──────────────────────────────────────────────────

    def query(self, keyword: str, category: str | None = None,
              project: str | None = None, limit: int = 10) -> list[MemoryEntry]:
        """Search memories by keyword."""
        results = []
        kw = keyword.lower()
        for entry in self._entries.values():
            if category and entry.category != category:
                continue
            if project and entry.project and entry.project != project:
                continue
            if kw in entry.key.lower() or kw in entry.value.lower():
                results.append(entry)
        results.sort(key=lambda e: (e.confidence, e.last_used), reverse=True)
        return results[:limit]

    def get_global_patterns(self) -> list[dict]:
        """Get patterns learned across all projects."""
        patterns = []
        for entry in self._entries.values():
            if entry.confidence >= PREFERENCE_CONFIDENCE_MIN:
                patterns.append({
                    "key": entry.key, "value": entry.value,
                    "confidence": entry.confidence,
                    "category": entry.category,
                })
        return sorted(patterns, key=lambda p: p["confidence"], reverse=True)

    # ── Maintenance ───────────────────────────────────────────────

    def prune_stale(self, max_age_days: int = MEMORY_DECAY_DAYS):
        """Remove memories older than the decay threshold."""
        cutoff = time.time() - (max_age_days * 86400)
        stale = [
            k for k, v in self._entries.items()
            if v.last_used < cutoff and v.confidence < PREFERENCE_CONFIDENCE_MIN
        ]
        for k in stale:
            del self._entries[k]
        if stale:
            self._save()
        return len(stale)

    def get_stats(self) -> dict:
        categories = defaultdict(int)
        for e in self._entries.values():
            categories[e.category] += 1
        return {
            "total_memories": len(self._entries),
            "preferences_learned": len(self.get_preferences()),
            "by_category": dict(categories),
            "stale_pruned": 0,
        }
