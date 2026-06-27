"""Agent Swarm — large-scale parallel agent dispatch with scatter/gather.

Extends AsyncSubAgentManager with swarm-specific patterns:
- scatter: dispatch one task to N agents in parallel
- gather: collect and deduplicate results
- broadcast: send same message to all agents
- pipeline: chain agents in sequence

Usage:
    swarm = AgentSwarm(agent_factory, max_agents=100)
    results = await swarm.scatter("Review this code for bugs", count=5)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_MAX_AGENTS = 100
DEFAULT_SCATTER_COUNT = 3
DEFAULT_TASK_TIMEOUT = 120.0
DEFAULT_BROADCAST_TIMEOUT = 60.0
PROMPT_PREVIEW_LENGTH = 50
CONSENSUS_PREFIX_LENGTH = 100
MIN_CONSENSUS = 0.0
MAX_CONSENSUS = 1.0


@dataclass
class SwarmTask:
    """A task dispatched to the swarm."""

    id: str
    prompt: str
    agent_id: str = ""
    status: str = "pending"  # pending, running, done, failed
    result: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmResult:
    """Aggregated result from a swarm operation."""

    tasks: list[SwarmTask] = field(default_factory=list)
    merged_result: str = ""
    consensus: float = MIN_CONSENSUS
    stats: dict[str, Any] = field(default_factory=dict)


class AgentSwarm:
    """Large-scale parallel agent dispatch with swarm patterns."""

    def __init__(self, agent_factory=None, max_agents: int = DEFAULT_MAX_AGENTS):
        self._agent_factory = agent_factory
        self._max_agents = max_agents
        self._tasks: dict[str, SwarmTask] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"swarm-{self._counter}"

    async def scatter(
        self,
        prompt: str,
        count: int = DEFAULT_SCATTER_COUNT,
        timeout: float = DEFAULT_TASK_TIMEOUT,
    ) -> SwarmResult:
        """Dispatch the same prompt to N agents in parallel.

        Use for: getting diverse perspectives, ensemble voting, coverage.
        """
        if count > self._max_agents:
            count = self._max_agents

        tasks = [SwarmTask(id=self._next_id(), prompt=prompt) for _ in range(count)]
        for t in tasks:
            self._tasks[t.id] = t

        async def _run_one(task: SwarmTask):
            task.status = "running"
            try:
                if self._agent_factory:
                    agent = self._agent_factory()
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: agent.run(task.prompt)),
                        timeout=timeout,
                    )
                    task.result = str(result) if result else ""
                    task.status = "done"
                else:
                    preview = task.prompt[:PROMPT_PREVIEW_LENGTH]
                    task.result = f"[Swarm] No agent factory. Prompt: {preview}..."
                    task.status = "done"
            except asyncio.TimeoutError:
                task.status = "failed"
                task.error = f"Timeout after {timeout}s"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

        await asyncio.gather(*[_run_one(t) for t in tasks])

        done = [t for t in tasks if t.status == "done"]
        failed = [t for t in tasks if t.status == "failed"]

        return SwarmResult(
            tasks=tasks,
            merged_result=self._merge_results([t.result for t in done]),
            consensus=self._calc_consensus([t.result for t in done]),
            stats={
                "total": len(tasks),
                "done": len(done),
                "failed": len(failed),
                "pattern": "scatter",
            },
        )

    async def gather(
        self,
        prompts: list[str],
        timeout: float = 120.0,
    ) -> SwarmResult:
        """Run different prompts on different agents, collect all results.

        Use for: parallel independent subtasks, divide-and-conquer.
        """
        if len(prompts) > self._max_agents:
            prompts = prompts[:self._max_agents]

        tasks = [SwarmTask(id=self._next_id(), prompt=p) for p in prompts]
        for t in tasks:
            self._tasks[t.id] = t

        async def _run_one(task: SwarmTask):
            task.status = "running"
            try:
                if self._agent_factory:
                    agent = self._agent_factory()
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: agent.run(task.prompt)),
                        timeout=timeout,
                    )
                    task.result = str(result) if result else ""
                    task.status = "done"
                else:
                    task.result = f"[Swarm] Prompt: {task.prompt[:PROMPT_PREVIEW_LENGTH]}..."
                    task.status = "done"
            except asyncio.TimeoutError:
                task.status = "failed"
                task.error = f"Timeout after {timeout}s"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

        await asyncio.gather(*[_run_one(t) for t in tasks])

        done = [t for t in tasks if t.status == "done"]
        return SwarmResult(
            tasks=tasks,
            merged_result="\n\n---\n\n".join(t.result for t in done),
            stats={
                "total": len(tasks),
                "done": len(done),
                "failed": len(tasks) - len(done),
                "pattern": "gather",
            },
        )

    async def broadcast(
        self,
        message: str,
        agent_ids: list[str] | None = None,
        timeout: float = DEFAULT_BROADCAST_TIMEOUT,
    ) -> dict[str, str]:
        """Send the same message to specific agents.

        Use for: notification, coordination, state sync.
        """
        results: dict[str, str] = {}
        targets = agent_ids or list(self._tasks.keys())
        if not targets:
            return {"status": "no agents available"}

        async def _notify(aid: str):
            try:
                task = self._tasks.get(aid)
                if task and self._agent_factory:
                    agent = self._agent_factory()
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: agent.run(message)),
                        timeout=timeout,
                    )
                    results[aid] = str(result)
                else:
                    results[aid] = "ack"
            except Exception as e:
                results[aid] = f"error: {e}"

        await asyncio.gather(*[_notify(aid) for aid in targets])
        return results

    def get_task(self, task_id: str) -> SwarmTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: str | None = None) -> list[SwarmTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    @staticmethod
    def _merge_results(results: list[str]) -> str:
        """Simple result merge — deduplicate and concatenate."""
        if not results:
            return ""
        if len(results) == 1:
            return results[0]
        # Deduplicate identical results
        unique = list(dict.fromkeys(results))
        return "\n\n---\n\n".join(unique)

    @staticmethod
    def _calc_consensus(results: list[str]) -> float:
        """Estimate consensus level among results (simple overlap heuristic)."""
        if len(results) < 2:
            return MAX_CONSENSUS
        # Simple: check if first 100 chars overlap
        prefixes = [r[:CONSENSUS_PREFIX_LENGTH].lower() for r in results if r]
        if not prefixes:
            return MIN_CONSENSUS
        most_common = max(set(prefixes), key=prefixes.count)
        return prefixes.count(most_common) / len(prefixes)
