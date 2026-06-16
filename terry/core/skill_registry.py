"""Skill Marketplace — community skill discovery and installation.

Discovers skills from a remote registry index. The registry is a simple
JSON file hosted in a Git repository. Users can search, install, and
update community-contributed skills.

Usage:
    registry = SkillRegistry()
    results = registry.search("code review")
    registry.install("terry-code-review")
    registry.list_remote()
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)

# Default registry — a simple JSON index in a GitHub repo
DEFAULT_REGISTRY = "https://raw.githubusercontent.com/terry-ai/skills/main/index.json"


@dataclass
class SkillInfo:
    """Metadata for a community skill."""
    name: str
    description: str = ""
    version: str = ""
    author: str = ""
    repo: str = ""  # Git URL for cloning
    tags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "repo": self.repo,
            "tags": self.tags or [],
        }


class SkillRegistry:
    """Client for the community skill marketplace.

    Reads a remote index.json to discover skills. Installs skills
    by cloning their Git repositories into the local skills directory.
    """

    def __init__(self, registry_url: str = DEFAULT_REGISTRY):
        self.registry_url = registry_url
        self._index: dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Fetch the registry index if not already loaded."""
        if self._loaded:
            return
        try:
            resp = httpx.get(self.registry_url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            self._index = resp.json()
        except Exception as e:
            logger.warning("Failed to load skill registry: %s", e)
            self._index = {}
        self._loaded = True

    def search(self, query: str) -> list[SkillInfo]:
        """Search available skills by name, description, or tags.

        Args:
            query: Search query string.

        Returns:
            List of matching SkillInfo objects.
        """
        self._ensure_loaded()
        results: list[SkillInfo] = []
        q = query.lower()
        skills = self._index.get("skills", [])
        for entry in skills:
            name = entry.get("name", "")
            desc = entry.get("description", "")
            tags = " ".join(entry.get("tags", []))
            if q in name.lower() or q in desc.lower() or q in tags.lower():
                results.append(SkillInfo(
                    name=name,
                    description=desc,
                    version=entry.get("version", ""),
                    author=entry.get("author", ""),
                    repo=entry.get("repo", ""),
                    tags=entry.get("tags", []),
                ))
        return results

    def list_remote(self) -> list[SkillInfo]:
        """List all available remote skills."""
        return self.search("")  # Empty query returns all

    def install(self, name: str, target_dir: Path | None = None) -> bool:
        """Install a community skill by cloning its Git repository.

        Args:
            name: Skill name matching the registry entry.
            target_dir: Directory to install into. Defaults to ./skills/.

        Returns:
            True if installed successfully.
        """
        self._ensure_loaded()
        entry = None
        for s in self._index.get("skills", []):
            if s.get("name") == name:
                entry = s
                break

        if not entry:
            logger.warning("Skill not found in registry: %s", name)
            return False

        repo = entry.get("repo", "")
        if not repo:
            logger.warning("Skill '%s' has no repo URL", name)
            return False

        target = target_dir or Path("./skills")
        target.mkdir(parents=True, exist_ok=True)

        dest = target / name
        if dest.exists():
            # Already installed — try updating
            try:
                subprocess.run(["git", "-C", str(dest), "pull"], capture_output=True, timeout=30)
                logger.info("Skill updated: %s", name)
                return True
            except Exception as e:
                logger.warning("Failed to update skill '%s': %s", name, e)
                return False

        try:
            subprocess.run(["git", "clone", repo, str(dest)], capture_output=True, timeout=60)
            logger.info("Skill installed: %s → %s", name, dest)
            return True
        except Exception as e:
            logger.warning("Failed to install skill '%s': %s", name, e)
            return False

    def update(self, name: str) -> bool:
        """Update an installed skill (git pull)."""
        target = Path("./skills") / name
        if not target.exists():
            logger.warning("Skill not installed: %s", name)
            return False
        try:
            subprocess.run(["git", "-C", str(target), "pull"], capture_output=True, timeout=30)
            logger.info("Skill updated: %s", name)
            return True
        except Exception as e:
            logger.warning("Failed to update skill '%s': %s", name, e)
            return False
