"""Skill marketplace - discover and install community skills.

Provides a registry for discovering, downloading, and managing
skills from remote repositories.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from .platform_utils import get_terry_dir


class SkillMarket:
    """Online skill marketplace client.

    Discovers skills from remote registries, downloads SKILL.md files,
    and manages installed community skills.
    """

    DEFAULT_REGISTRY = "https://raw.githubusercontent.com/terry-ai/skills/main/registry.json"

    def __init__(
        self,
        registry_url: str | None = None,
        install_dir: Path | None = None,
    ):
        self.registry_url = registry_url or self.DEFAULT_REGISTRY
        self.install_dir = install_dir or get_terry_dir("skills")
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self._registry: list[dict[str, str]] = []
        self._loaded = False

    def fetch_registry(self) -> list[dict[str, str]]:
        """Fetch the skill registry from the remote server.

        Returns list of available skills with metadata.
        """
        try:
            response = httpx.get(self.registry_url, timeout=15)
            if response.status_code == 200:
                self._registry = response.json()
                self._loaded = True
                return self._registry
        except Exception:
            pass

        # Fallback: return cached or empty
        return self._registry

    def search(self, query: str) -> list[dict[str, str]]:
        """Search the registry for matching skills.

        Args:
            query: Search term

        Returns:
            List of matching skills
        """
        if not self._loaded:
            self.fetch_registry()

        q = query.lower()
        return [
            skill for skill in self._registry
            if q in skill.get("name", "").lower() or
               q in skill.get("description", "").lower() or
               any(q in t.lower() for t in skill.get("tags", []))
        ]

    def list_available(self) -> list[dict[str, str]]:
        """List all available skills in the registry."""
        if not self._loaded:
            self.fetch_registry()
        return self._registry

    def install(self, skill_name: str) -> bool:
        """Install a skill from the registry.

        Args:
            skill_name: Name of the skill to install

        Returns:
            True if installed successfully
        """
        if not self._loaded:
            self.fetch_registry()

        # Find skill in registry
        skill_meta = None
        for s in self._registry:
            if s.get("name") == skill_name:
                skill_meta = s
                break

        if not skill_meta:
            return False

        download_url = skill_meta.get("url", "")
        if not download_url:
            return False

        try:
            response = httpx.get(download_url, timeout=30)
            if response.status_code != 200:
                return False

            skill_dir = self.install_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(response.text, encoding="utf-8")

            return True

        except Exception:
            return False

    def uninstall(self, skill_name: str) -> bool:
        """Remove an installed community skill.

        Args:
            skill_name: Name of the skill to remove

        Returns:
            True if removed
        """
        skill_dir = self.install_dir / skill_name
        if not skill_dir.exists():
            return False

        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            skill_file.unlink()

        try:
            skill_dir.rmdir()
        except Exception:
            pass

        return True

    def list_installed(self) -> list[dict[str, str]]:
        """List locally installed community skills."""
        installed = []
        for skill_dir in self.install_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                installed.append({
                    "name": skill_dir.name,
                    "path": str(skill_dir),
                    "size": skill_file.stat().st_size,
                })
        return installed

    def get_skill_info(self, skill_name: str) -> dict[str, Any] | None:
        """Get detailed information about a skill."""
        if not self._loaded:
            self.fetch_registry()

        for s in self._registry:
            if s.get("name") == skill_name:
                return s
        return None
