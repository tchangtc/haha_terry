"""System prompt composer — composable prompt chunks with chain-of-use API.

Inspired by merco's PromptBuilder pattern: each section of the system
prompt is a self-contained ``PromptChunk`` that can be independently
enabled/disabled, tested, and reordered.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Prompt Context ────────────────────────────────────────────────

@dataclass
class PromptContext:
    """Immutable snapshot of agent state for prompt building.

    All chunks receive this context and decide whether to contribute
    content based on what is available (e.g. skip Memory chunk when
    no memories exist).
    """

    workdir: str
    tools: list[Any] = field(default_factory=list)
    active_skill: str | None = None
    skill_manager: Any = None
    memory: Any = None
    session: Any = None


# ── Prompt Chunk base ─────────────────────────────────────────────

class PromptChunk(ABC):
    """A composable piece of the system prompt.

    Subclasses implement ``build()`` which returns a string to append
    to the prompt, or ``None`` / ``""`` to skip this chunk.
    """

    enabled: bool = True

    @abstractmethod
    def build(self, ctx: PromptContext) -> str | None:
        """Return prompt text or None to skip."""
        ...


# ── Concrete Chunks ───────────────────────────────────────────────

class IdentityChunk(PromptChunk):
    """Core identity — who the agent is and where it works."""

    def build(self, ctx: PromptContext) -> str:
        return (
            f"You are Terry, a production-grade AI coding agent working in {ctx.workdir}.\n"
            "You have access to powerful tools for file operations, code search, and system commands.\n"
        )


class GuidelinesChunk(PromptChunk):
    """Behavioral guidelines for the agent."""

    def build(self, ctx: PromptContext) -> str:
        return (
            "## Guidelines\n"
            "- Use tools to solve tasks efficiently\n"
            "- Be concise and helpful in your responses\n"
            "- Explain your reasoning when appropriate\n"
            "- Ask for clarification if the task is unclear\n"
        )


class ToolListChunk(PromptChunk):
    """List of available tools with descriptions."""

    def build(self, ctx: PromptContext) -> str | None:
        if not ctx.tools:
            return None
        lines = ["## Available Tools"]
        for tool in ctx.tools:
            lines.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(lines)


class ActiveSkillChunk(PromptChunk):
    """Currently active skill instructions (injected when a skill is active)."""

    def build(self, ctx: PromptContext) -> str | None:
        if not ctx.active_skill or not ctx.skill_manager:
            return None
        skill = ctx.skill_manager.get_skill(ctx.active_skill)
        if not skill:
            return None
        return (
            "## Active Skill\n"
            f"{ctx.skill_manager.get_skill_context(skill)}"
        )


class SkillListChunk(PromptChunk):
    """List of available skills for quick reference."""

    def build(self, ctx: PromptContext) -> str | None:
        if not ctx.skill_manager:
            return None
        skills = ctx.skill_manager.list_skills()
        if not skills:
            return None
        lines = [
            "## Available Skills",
            "You have access to the following specialized skills:",
        ]
        for skill in skills:
            lines.append(f"- **{skill.name}**: {skill.description}")
        lines.append("")
        lines.append("When a user request matches a skill's purpose, follow the skill's instructions.")
        return "\n".join(lines)


class MemoryChunk(PromptChunk):
    """Persistent memory index — first 10 entries + nudge to persist new knowledge."""

    MAX_ENTRIES = 10

    def build(self, ctx: PromptContext) -> str | None:
        if not ctx.memory:
            return None
        memory_list = ctx.memory.list_memories()
        if not memory_list:
            return None
        lines = [
            "## Your Memories",
            "You have persistent memories from previous sessions:",
        ]
        for mem in memory_list[: self.MAX_ENTRIES]:
            lines.append(f"- **{mem['name']}**: {mem['description']}")
        lines.extend([
            "",
            "💡 Periodically persist useful knowledge to memory so it survives "
            "context compaction and carries across sessions. Use [[wiki-links]] "
            "to connect related memories.",
        ])
        return "\n".join(lines)


class SessionChunk(PromptChunk):
    """Current session metadata."""

    def build(self, ctx: PromptContext) -> str | None:
        if not ctx.session:
            return None
        return (
            "## Current Session\n"
            f"Session ID: {ctx.session.session_id}\n"
            f"Messages in session: {len(ctx.session.get_messages())}"
        )


# ── Prompt Composer ───────────────────────────────────────────────

class PromptComposer:
    """Chain-of-use API for building system prompts from chunks.

    Usage::

        composer = PromptComposer()
        composer.use(IdentityChunk())
        composer.use(GuidelinesChunk())
        composer.use(ToolListChunk())
        prompt = composer.build(ctx)

    Chunks can be selectively disabled::

        composer.disable("memory")
    """

    def __init__(self) -> None:
        self._chunks: list[PromptChunk] = [
            IdentityChunk(),
            GuidelinesChunk(),
            ToolListChunk(),
            ActiveSkillChunk(),
            SkillListChunk(),
            MemoryChunk(),
            SessionChunk(),
        ]

    def use(self, chunk: PromptChunk, position: int | None = None) -> "PromptComposer":
        """Add a chunk. If *position* is given, insert at that index."""
        if position is None:
            self._chunks.append(chunk)
        else:
            self._chunks.insert(position, chunk)
        return self

    def disable(self, chunk_class_name: str) -> "PromptComposer":
        """Disable a chunk by its class name (e.g. ``"MemoryChunk"``)."""
        name_lower = chunk_class_name.lower()
        for chunk in self._chunks:
            if type(chunk).__name__.lower() == name_lower:
                chunk.enabled = False
        return self

    def enable(self, chunk_class_name: str) -> "PromptComposer":
        """Re-enable a previously disabled chunk."""
        name_lower = chunk_class_name.lower()
        for chunk in self._chunks:
            if type(chunk).__name__.lower() == name_lower:
                chunk.enabled = True
        return self

    def build(self, ctx: PromptContext) -> str:
        """Assemble the full system prompt from all enabled chunks."""
        parts: list[str] = []
        for chunk in self._chunks:
            if not chunk.enabled:
                continue
            text = chunk.build(ctx)
            if text:
                parts.append(text)
        return "\n\n".join(parts)


# ── Convenience function (backward-compatible) ────────────────────

# Module-level singleton for the default composer
_default_composer = PromptComposer()


def build_system_prompt(
    workdir: str,
    tools: list[Any],
    active_skill: str | None = None,
    skill_manager: Any = None,
    memory: Any = None,
    session: Any = None,
) -> str:
    """Build the system prompt using the default composer.

    Maintains backward compatibility with the original signature while
    delegating to the composable chunk system internally.
    """
    ctx = PromptContext(
        workdir=workdir,
        tools=tools,
        active_skill=active_skill,
        skill_manager=skill_manager,
        memory=memory,
        session=session,
    )
    return _default_composer.build(ctx)


def get_composer() -> PromptComposer:
    """Get the default composer for customization.

    Usage::

        composer = get_composer()
        composer.disable("SessionChunk")
        composer.use(MyCustomChunk(), position=2)
    """
    return _default_composer
