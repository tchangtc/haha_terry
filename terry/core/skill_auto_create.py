"""Skill auto-creation — learn reusable skills from complex task trajectories.

Inspired by hermes-agent's ``SkillAutoCreator`` closed learning loop.

When an Agent completes a complex task (many tool calls, many turns, or
explicit user request), the ``SkillAutoCreator`` analyzes the conversation
trajectory and extracts a reusable skill template — a ``SKILL.md`` file
with YAML frontmatter — that can be activated by future Agent sessions.

This is the core differentiator for Terry v0.4.0: the Agent that learns
from experience.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .platform_utils import get_terry_dir

logger = logging.getLogger(__name__)

# ── Thresholds ──────────────────────────────────────────────────────

DEFAULT_MIN_TOOL_CALLS = 5       # Create skill only when ≥ N tool calls
DEFAULT_MIN_TURNS = 3            # Create skill only when ≥ N conversation turns
DEFAULT_MAX_SKILLS_PER_SESSION = 3  # Avoid flooding the skill directory

# Directory for auto-created skills (separate from bundled/manual skills)
AUTO_SKILLS_DIR_NAME = "auto-created"


class SkillAutoCreator:
    """Analyzes conversation trajectories and extracts reusable skills.

    The life cycle:
      1. Agent completes a task → ``run()`` calls ``maybe_create()``
      2. Complexity is assessed against thresholds
      3. If the task was complex enough, the LLM extracts a skill template
      4. The template is saved as a ``SKILL.md`` file
      5. Future sessions can activate the skill via the SkillManager

    Args:
        skills_base_dir: Root skills directory (auto-created skills land in
            a subdirectory ``auto-created/``).
        min_tool_calls: Minimum tool calls before skill creation triggers.
        min_turns: Minimum conversation turns before skill creation triggers.
        llm_client: LLMClient-compatible object with a ``chat()`` method
            for extraction calls.  If ``None``, extraction is skipped.
    """

    def __init__(
        self,
        skills_base_dir: Path | None = None,
        min_tool_calls: int = DEFAULT_MIN_TOOL_CALLS,
        min_turns: int = DEFAULT_MIN_TURNS,
        llm_client: Any = None,
    ) -> None:
        self.skills_base_dir = skills_base_dir or get_terry_dir("skills")
        self.auto_dir = self.skills_base_dir / AUTO_SKILLS_DIR_NAME
        self.auto_dir.mkdir(parents=True, exist_ok=True)
        self.min_tool_calls = min_tool_calls
        self.min_turns = min_turns
        self.llm_client = llm_client
        self._session_skill_count = 0

    def maybe_create(
        self,
        user_message: str,
        messages: list[dict[str, Any]],
        tool_call_count: int,
        agent_response: str,
        max_per_session: int = DEFAULT_MAX_SKILLS_PER_SESSION,
    ) -> str | None:
        """Assess conversation complexity and optionally create a skill.

        Called after the Agent loop exits.  Returns the skill name if one
        was created, or ``None`` if thresholds were not met.

        Args:
            user_message: The original user prompt that started the task.
            messages: Full conversation messages list.
            tool_call_count: Number of tool calls made during the task.
            agent_response: Final assistant response text.
            max_per_session: Max auto-created skills per session.

        Returns:
            Skill name if created, else ``None``.
        """
        # ── Guard: already hit session cap ─────────────────────────
        if self._session_skill_count >= max_per_session:
            return None

        # ── Assess complexity ──────────────────────────────────────
        turns = sum(1 for m in messages if m.get("role") == "assistant")
        if tool_call_count < self.min_tool_calls and turns < self.min_turns:
            return None

        # ── Extract via LLM ─────────────────────────────────────────
        skill_data = self._extract_skill(user_message, agent_response, tool_call_count)
        if skill_data is None:
            return None

        # ── Save ────────────────────────────────────────────────────
        filename = self._save_skill(skill_data)
        self._session_skill_count += 1
        logger.info(
            "Auto-created skill: %s (tool calls: %d, turns: %d)",
            skill_data.get("name", "unknown"),
            tool_call_count,
            turns,
        )
        return filename

    # ── Private ──────────────────────────────────────────────────────

    def _extract_skill(
        self,
        user_message: str,
        agent_response: str,
        tool_call_count: int,
    ) -> dict[str, Any] | None:
        """Use the LLM to extract a reusable skill from the trajectory.

        Returns a dict with YAML frontmatter keys + ``content`` key, or
        ``None`` if extraction fails / LLM is unavailable.
        """
        if self.llm_client is None:
            # No LLM available — use a simple heuristic extraction
            return self._heuristic_extract(user_message, agent_response)

        extraction_prompt = (
            "You are a skill extraction system. Given a task description "
            "and its result, extract a reusable skill in YAML+markdown format.\n\n"
            "Output ONLY valid YAML frontmatter followed by markdown instructions.\n"
            "The frontmatter MUST contain:\n"
            "  name: (kebab-case slug)\n"
            "  description: (one-line summary)\n"
            "  triggers: (list of trigger phrases)\n\n"
            f"Task: {user_message[:500]}\n"
            f"Result summary: {agent_response[:1000]}\n"
            f"Tool calls made: {tool_call_count}\n\n"
            "---\n"
            "name: \n"
            "description: \n"
            "triggers: []\n"
            "---\n"
        )

        try:
            response = self.llm_client.chat(
                messages=[{"role": "user", "content": extraction_prompt}],
                system="You are a skill extraction assistant. Output only valid YAML+markdown.",
                max_tokens=2000,
            )
            text = self._extract_text(response)
            return self._parse_skill_output(text)
        except Exception:
            logger.warning("LLM extraction failed, falling back to heuristic", exc_info=True)
            return self._heuristic_extract(user_message, agent_response)

    @staticmethod
    def _heuristic_extract(user_message: str, agent_response: str) -> dict[str, Any] | None:
        """Simple heuristic extraction when no LLM is available."""
        # Use the user message as a trigger and generate basic scaffolding
        name = "auto-" + "".join(
            c if c.isalnum() else "-" for c in user_message[:40].lower()
        ).strip("-")
        if len(name) < 5:
            return None

        return {
            "name": name,
            "description": user_message[:200].strip(),
            "triggers": [user_message[:80].strip()],
            "content": (
                f"# Auto-generated Skill\n\n"
                f"This skill was automatically created after a complex task.\n\n"
                f"## Original Request\n{user_message[:500]}\n\n"
                f"## Approach\n{agent_response[:1000]}\n\n"
                f"## Usage\n"
                f"When a similar task is requested, follow the approach above.\n"
            ),
        }

    @staticmethod
    def _parse_skill_output(text: str) -> dict[str, Any] | None:
        """Parse LLM output that should be YAML frontmatter + markdown."""
        if not text.startswith("---"):
            return None
        parts = text.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            fm = yaml.safe_load(parts[1])
            if not isinstance(fm, dict) or "name" not in fm:
                return None
            fm["content"] = parts[2].strip()
            return fm
        except Exception:
            return None

    def _save_skill(self, skill_data: dict[str, Any]) -> str:
        """Write a SKILL.md file and return the filename."""
        name = skill_data.get("name", "unnamed")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
        filename = f"{safe_name}.md"

        frontmatter = {
            "name": name,
            "description": skill_data.get("description", ""),
            "triggers": skill_data.get("triggers", []),
            "metadata": {
                "auto_created": True,
                "created_at": datetime.now().isoformat(),
                "source": "SkillAutoCreator",
            },
        }

        content = skill_data.get("content", "").strip()

        md = f"---\n{yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)}---\n\n{content}\n"

        filepath = self.auto_dir / filename
        filepath.write_text(md, encoding="utf-8")
        return filename

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text from an LLM response dict."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            content = response.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
        return ""


# ── Convenience factory ─────────────────────────────────────────────

_auto_creator: SkillAutoCreator | None = None


def get_skill_auto_creator(
    skills_base_dir: Path | None = None,
    llm_client: Any = None,
) -> SkillAutoCreator:
    """Get or create the global SkillAutoCreator instance."""
    global _auto_creator
    if _auto_creator is None:
        _auto_creator = SkillAutoCreator(
            skills_base_dir=skills_base_dir,
            llm_client=llm_client,
        )
    return _auto_creator


def reset_skill_auto_creator() -> None:
    """Reset the global SkillAutoCreator (for testing)."""
    global _auto_creator
    _auto_creator = None
