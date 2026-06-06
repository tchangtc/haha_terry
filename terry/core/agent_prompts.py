"""System prompt builder — extracted from Agent.build_system_prompt()."""

from __future__ import annotations

from typing import Any


def build_system_prompt(
    workdir: str,
    tools: list[Any],
    active_skill: str | None = None,
    skill_manager: Any = None,
    memory: Any = None,
    session: Any = None,
) -> str:
    """Build comprehensive system prompt with context.

    Args:
        workdir: Working directory path
        tools: List of tool objects (must have .name and .description)
        active_skill: Currently active skill name
        skill_manager: SkillManager instance (optional)
        memory: Memory instance (optional)
        session: Session instance (optional)

    Returns:
        System prompt string
    """
    parts = [
        f"You are Terry, a production-grade AI coding agent working in {workdir}.",
        "You have access to powerful tools for file operations, code search, and system commands.",
        "",
        "## Guidelines",
        "- Use tools to solve tasks efficiently",
        "- Be concise and helpful in your responses",
        "- Explain your reasoning when appropriate",
        "- Ask for clarification if the task is unclear",
        "",
        "## Available Tools",
    ]

    for tool in tools:
        parts.append(f"- **{tool.name}**: {tool.description}")

    if active_skill and skill_manager:
        skill = skill_manager.get_skill(active_skill)
        if skill:
            skill_context = skill_manager.get_skill_context(skill)
            parts.extend([
                "",
                "## Active Skill",
                skill_context,
            ])

    if skill_manager:
        skills = skill_manager.list_skills()
        if skills:
            parts.extend([
                "",
                "## Available Skills",
                "You have access to the following specialized skills:",
            ])
            for skill in skills:
                parts.append(f"- **{skill.name}**: {skill.description}")
            parts.append("")
            parts.append("When a user request matches a skill's purpose, follow the skill's instructions.")

    if memory:
        memory_list = memory.list_memories()
        if memory_list:
            parts.extend([
                "",
                "## Your Memories",
                "You have persistent memories from previous sessions:",
            ])
            for mem in memory_list[:10]:
                parts.append(f"- **{mem['name']}**: {mem['description']}")

    if session:
        parts.extend([
            "",
            "## Current Session",
            f"Session ID: {session.session_id}",
            f"Messages in session: {len(session.get_messages())}",
        ])

    return "\n".join(parts)
