"""Typing protocols for Terry — lightweight structural interfaces.

These Protocol classes enable structural subtyping (PEP 544) so that
functions can accept any object matching the expected interface without
requiring direct inheritance from a concrete class.

This replaces the widespread `agent: Any` pattern with `agent: AgentLike`,
improving type safety while preserving the loose coupling between modules
that makes the CLI / harness / workflow layers composable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentLike(Protocol):
    """Structural interface for any Agent-compatible object.

    Any object with a `run(user_message: str) -> str` method satisfies
    this protocol, regardless of its actual class. This includes:
      - terry.core.agent.Agent
      - terry.core.async_agent.AsyncAgent
      - Mock agents in tests
      - Custom wrappers around the agent

    The `config` attribute is NOT part of the protocol — consumers
    should accept the agent through this protocol and not reach into
    its internals.
    """

    def run(self, user_message: str, use_cache: bool = True) -> str: ...

    def get_mode(self) -> str: ...

    def reset(self) -> None: ...
