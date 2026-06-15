"""Skill system for Terry - dynamic loading and execution of skills."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Represents a skill that can be loaded and executed."""

    name: str
    description: str
    content: str
    triggers: list[str] = field(default_factory=list)
    path: Path | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, skill_path: Path) -> Skill | None:
        """Load a skill from a SKILL.md file.

        Args:
            skill_path: Path to the SKILL.md file

        Returns:
            Skill object or None if loading failed
        """
        try:
            content = skill_path.read_text(encoding="utf-8")

            # Parse YAML frontmatter
            if not content.startswith("---"):
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                return None

            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return None

            name = frontmatter.get("name", skill_path.parent.name)
            description = frontmatter.get("description", "")
            triggers = frontmatter.get("triggers", [])

            # Remove frontmatter from content
            skill_content = parts[2].strip()

            return cls(
                name=name,
                description=description,
                content=skill_content,
                triggers=triggers,
                path=skill_path,
                metadata=frontmatter,
            )
        except Exception as e:
            logger.error("Error loading skill from %s: %s", skill_path, e)
            return None


class SkillManager:
    """Manages loading, matching, and execution of skills."""

    def __init__(self, skills_dirs: list[Path]):
        """Initialize skill manager.

        Args:
            skills_dirs: List of directories to search for skills
        """
        self.skills_dirs = skills_dirs
        self.skills: dict[str, Skill] = {}
        self._load_skills()

    def _load_skills(self):
        """Load all skills from configured directories."""
        for skills_dir in self.skills_dirs:
            if not skills_dir.exists():
                continue

            # Search for SKILL.md files
            for skill_file in skills_dir.rglob("SKILL.md"):
                skill = Skill.from_file(skill_file)
                if skill:
                    self.skills[skill.name] = skill

    def reload(self):
        """Reload all skills from disk."""
        self.skills.clear()
        self._load_skills()

    reload_skills = reload  # alias

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill object or None if not found
        """
        return self.skills.get(name)

    def list_skills(self) -> list[Skill]:
        """List all available skills.

        Returns:
            List of all loaded skills
        """
        return list(self.skills.values())

    def match_skill(self, user_input: str) -> Skill | None:
        """Match user input to the most appropriate skill.

        Args:
            user_input: User's input text

        Returns:
            Matched skill or None
        """
        user_input_lower = user_input.lower()

        # First, check explicit triggers
        for skill in self.skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in user_input_lower:
                    return skill

        # Then, check skill names and descriptions
        for skill in self.skills.values():
            if skill.name.lower() in user_input_lower:
                return skill
            if skill.description.lower() in user_input_lower:
                return skill

        return None

    def get_skill_context(self, skill: Skill) -> str:
        """Get the context to inject into the system prompt for a skill.

        Args:
            skill: Skill to get context for

        Returns:
            Formatted context string
        """
        context = f"""
# Active Skill: {skill.name}

{skill.description}

## Instructions

{skill.content}
"""
        return context


class SkillExecutor:
    """Executes skills by coordinating tools and LLM calls."""

    def __init__(self, skill_manager: SkillManager, agent):
        """Initialize skill executor.

        Args:
            skill_manager: Skill manager instance
            agent: Agent instance for tool access
        """
        self.skill_manager = skill_manager
        self.agent = agent

    def execute_skill(self, skill: Skill, user_input: str) -> str:
        """Execute a skill with the given user input.

        Args:
            skill: Skill to execute
            user_input: User's input

        Returns:
            Execution result
        """
        # Inject skill context by activating the skill on the agent
        # Skill context is injected via build_system_prompt() which checks active_skill
        previous_skill = self.agent.active_skill
        self.agent.active_skill = skill.name

        try:
            # Run the agent with the skill context
            result = self.agent.run(user_input)
            return result
        finally:
            # Restore previous skill state
            self.agent.active_skill = previous_skill



# SkillWatcher — polling-based hot reload
class SkillWatcher:
    POLL_INTERVAL = 3.0
    def __init__(self, skills_dirs, on_change=None):
        self.skills_dirs = [Path(d) for d in skills_dirs]
        self._last_mtimes = {}; self._on_change = on_change
        self._running = False; self._thread = None
    def start(self):
        if self._running: return
        self._snapshot_mtimes(); self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="skill-watcher")
        self._thread.start()
    def stop(self): self._running = False
    def _snapshot_mtimes(self):
        for d in self.skills_dirs:
            if d.exists():
                for sf in d.rglob("SKILL.md"): self._last_mtimes[sf] = sf.stat().st_mtime
    def _poll_loop(self):
        while self._running:
            try:
                changed = False
                for d in self.skills_dirs:
                    if not d.exists(): continue
                    for sf in d.rglob("SKILL.md"):
                        cur = sf.stat().st_mtime
                        if self._last_mtimes.get(sf, 0) < cur: self._last_mtimes[sf] = cur; changed = True
                if changed and self._on_change: self._on_change()
            except Exception:
                logger.debug("Skill watcher poll error", exc_info=True)
            time.sleep(self.POLL_INTERVAL)

# Global skill manager instance
_skill_manager: SkillManager | None = None


def get_skill_manager(skills_dirs: list[Path] | None = None) -> SkillManager:
    """Get or create the global skill manager instance.

    Args:
        skills_dirs: Optional list of skill directories

    Returns:
        SkillManager instance
    """
    global _skill_manager
    if _skill_manager is None:
        if skills_dirs is None:
            # Default skill directories
            skills_dirs = [
                get_terry_dir("skills"),
                Path.cwd() / "skills",
            ]
        _skill_manager = SkillManager(skills_dirs)
    return _skill_manager


def set_skill_manager(instance: SkillManager) -> None:
    """Inject a custom SkillManager instance (for testing/DI)."""
    global _skill_manager
    _skill_manager = instance


def reset_skill_manager() -> None:
    """Reset skill manager singleton (forces re-initialization on next get)."""
    global _skill_manager
    _skill_manager = None
