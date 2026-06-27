"""Shared Sessions — multi-agent shared context and collaboration.

Extends the existing Session to allow multiple agents to read/write
a shared conversation context with locking and conflict detection.

Usage:
    session = SharedSession("team-review")
    session.add_agent_message("reviewer", "Found 3 issues in auth.py")
    context = session.get_shared_context()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_MAX_CONTEXT_TOKENS = 200000
DEFAULT_AGENT_CONTEXT_TOKENS = 50000
ESTIMATED_TOKENS_PER_WORD = 1.3


class AgentRole(StrEnum):
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"
    COORDINATOR = "coordinator"


@dataclass
class SharedMessage:
    """A message in a shared session, attributed to a specific agent."""

    role: str  # user, assistant, system
    agent_id: str = ""
    agent_role: AgentRole | None = None
    content: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """State of an agent in the shared session."""

    agent_id: str
    role: AgentRole = AgentRole.DEVELOPER
    status: str = "idle"  # idle, working, blocked, done
    current_task: str = ""
    joined_at: float = field(default_factory=time.time)


class SharedSession:
    """Multi-agent shared session with context isolation and locking."""

    def __init__(self, session_id: str, max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS):
        self.id = session_id
        self._max_context_tokens = max_context_tokens
        self._messages: list[SharedMessage] = []
        self._agents: dict[str, AgentState] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._created_at = time.time()

    # ── Agent Management ──────────────────────────────────────────

    def join(self, agent_id: str, role: AgentRole = AgentRole.DEVELOPER) -> AgentState:
        """Register an agent in the shared session."""
        state = AgentState(agent_id=agent_id, role=role)
        self._agents[agent_id] = state
        self._add_system_message(f"Agent '{agent_id}' joined as {role.value}")
        return state

    def leave(self, agent_id: str):
        """Remove an agent from the session."""
        self._agents.pop(agent_id, None)
        self._add_system_message(f"Agent '{agent_id}' left the session")

    def get_agents(self) -> list[AgentState]:
        return list(self._agents.values())

    def update_agent_status(self, agent_id: str, status: str, task: str = ""):
        if agent_id in self._agents:
            self._agents[agent_id].status = status
            self._agents[agent_id].current_task = task

    # ── Message Operations ─────────────────────────────────────────

    async def add_agent_message(
        self, agent_id: str, content: str, role: str = "assistant"
    ):
        """Add a message from an agent, with locking."""
        async with self._locks[agent_id]:
            agent = self._agents.get(agent_id)
            self._messages.append(SharedMessage(
                role=role,
                agent_id=agent_id,
                agent_role=agent.role if agent else None,
                content=content,
            ))

    def add_user_message(self, content: str):
        """Add a message from the human user."""
        self._messages.append(SharedMessage(
            role="user", agent_id="human", content=content,
        ))

    def _add_system_message(self, content: str):
        self._messages.append(SharedMessage(
            role="system", content=content,
        ))

    def get_messages(self, limit: int | None = None) -> list[SharedMessage]:
        """Get all shared messages, optionally limited."""
        if limit:
            return self._messages[-limit:]
        return list(self._messages)

    # ── Context Management ─────────────────────────────────────────

    def get_shared_context(self, agent_id: str, max_tokens: int = DEFAULT_AGENT_CONTEXT_TOKENS) -> list[dict]:
        """Get the shared context formatted for a specific agent.

        Includes only messages visible to this agent.
        """
        # All messages are visible for now (full transparency)
        context = []
        token_estimate = 0
        for msg in reversed(self._messages):
            entry = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.agent_id and msg.agent_id != agent_id:
                entry["content"] = f"[{msg.agent_id}]: {msg.content}"
            context.insert(0, entry)
            token_estimate += len(msg.content.split())
            if token_estimate >= max_tokens:
                break
        return context

    def get_agent_context(self, agent_id: str) -> dict[str, Any]:
        """Get context specific to one agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return {"error": f"Agent '{agent_id}' not in session"}
        my_messages = [
            m for m in self._messages
            if m.agent_id == agent_id
        ]
        return {
            "agent": agent,
            "message_count": len(my_messages),
            "total_messages": len(self._messages),
            "peers": [a.agent_id for a in self._agents.values() if a.agent_id != agent_id],
        }

    # ── Stats ──────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "session_id": self.id,
            "agent_count": len(self._agents),
            "message_count": len(self._messages),
            "uptime_seconds": time.time() - self._created_at,
            "agents": {
                aid: {"role": s.role.value, "status": s.status}
                for aid, s in self._agents.items()
            },
        }
