"""Agent hooks — extracted cross-cutting concerns from Agent.run().

Keeps the main run loop lean by extracting:
  - _pre_process: FTS indexing, @mention, skill matching
  - _post_process: summary, tips, feedback, knowledge tracking, skill auto-creation
"""

from __future__ import annotations

import re
import time
from typing import Any


def pre_process(agent: Any, user_message: str) -> str:
    """Process user message before the ReAct loop.

    Returns enriched message with injected context.
    """
    enriched = user_message

    # FTS index
    if agent.fts_search:
        sid = agent.session.session_id if agent.session else "default"
        agent.fts_search.index_message(sid, "user", user_message)

    # @mention context injection
    enriched = agent.parse_mentions(user_message)

    # Skill auto-match
    if agent.skill_manager:
        matched = agent.skill_manager.match_skill(enriched)
        if matched:
            agent.active_skill = matched.name

    return enriched


def post_process(agent: Any, user_message: str, response_text: str, start_time: float) -> str:
    """Enrich agent response after the ReAct loop completes."""
    result = response_text

    # FTS index assistant response
    if agent.fts_search:
        sid = agent.session.session_id if agent.session else "default"
        agent.fts_search.index_message(sid, "assistant", result)

    # UX summary + tips
    from .ux import TipsEngine, UXFormatter
    result += UXFormatter.summary(agent)
    tip = TipsEngine.get_tip_for_context(message=user_message)
    if tip:
        result += f"\n{UXFormatter.tip(tip)}"

    # Proactive suggestions
    if agent.suggester and agent.suggester.should_suggest(agent.messages):
        suggestions = agent.suggester.analyze(agent.messages)
        if suggestions:
            result += "\n" + agent.suggester.format_suggestions(suggestions)

    # Knowledge tracking
    if agent.knowledge_graph:
        _track_knowledge(agent, user_message, response_text)

    # Skill auto-creation
    if agent.skill_auto_creator:
        suggestion = agent.skill_auto_creator.analyze_conversation(user_message, response_text)
        if suggestion and suggestion.get("confidence", 0) >= 0.7:
            agent.skill_auto_creator.create_skill(suggestion, response_text)

    # Non-blocking feedback
    agent.feedback.maybe_prompt(
        user_message=user_message, assistant_response=response_text,
        session_id=agent.session.session_id if agent.session else "",
        tool_calls=agent.tool_call_count,
        duration_ms=(time.time() - start_time) * 1000,
    )

    return result


def _track_knowledge(agent: Any, user_msg: str, assistant_msg: str) -> None:
    """Extract entities from conversation and add to knowledge graph."""
    combined = user_msg + " " + assistant_msg
    files = set(re.findall(r"['\"]?([\\w./-]+\\.(?:py|js|ts|md|yaml|json))['\"]?", combined))
    for f in files:
        agent.knowledge_graph.add_node(f"file:{f}", "file", name=f)
