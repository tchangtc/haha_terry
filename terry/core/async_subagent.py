"""Async SubAgent manager — true asyncio-based sub-agent execution."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AsyncSubAgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"  # Provider incompatible — task not executed, needs inline fallback


@dataclass
class AsyncSubAgent:
    """A truly async sub-agent that runs in the event loop."""
    id: str = field(default_factory=lambda: f"as_{uuid.uuid4().hex[:8]}")
    prompt: str = ""
    status: AsyncSubAgentStatus = AsyncSubAgentStatus.PENDING
    result: str | None = None
    error: str | None = None
    tool_calls: int = 0
    tokens_used: int = 0
    started_at: str = ""
    completed_at: str = ""
    parent_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parent_id": self.parent_id,
        }


class AsyncSubAgentManager:
    """Manages truly async sub-agents with asyncio.

    Replaces threading-based SubAgentManager with:
    - True non-blocking execution
    - Better concurrency (100+ concurrent sub-agents)
    - Lower memory overhead
    - Better error handling and cancellation
    """

    def __init__(
        self,
        agent_factory: Callable | None = None,
        max_concurrent: int = 50,
        default_timeout: float = 300.0,
    ):
        self.agent_factory = agent_factory
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self._agents: dict[str, AsyncSubAgent] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore: asyncio.Semaphore | None = None
        self._running = False

    async def start(self) -> None:
        """Start the manager."""
        self._running = True
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

    async def stop(self) -> None:
        """Stop all running sub-agents."""
        self._running = False
        # Cancel all running tasks
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        # Wait for all to finish
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def spawn(
        self,
        prompt: str,
        timeout: float | None = None,
        parent_id: str | None = None,
    ) -> str:
        """Spawn a new async sub-agent.

        Args:
            prompt: Task prompt
            timeout: Timeout in seconds
            parent_id: Parent agent ID (for tracking)

        Returns:
            Sub-agent ID
        """
        timeout = timeout or self.default_timeout

        sub_agent = AsyncSubAgent(
            prompt=prompt,
            parent_id=parent_id,
        )
        self._agents[sub_agent.id] = sub_agent

        # Create async task
        task = asyncio.create_task(
            self._run_sub_agent(sub_agent, timeout)
        )
        self._tasks[sub_agent.id] = task

        # Register with background task registry for unified monitoring
        try:
            from .background_registry import BackgroundTask, get_background_registry
            get_background_registry().register(BackgroundTask(
                id=sub_agent.id,
                description=prompt[:120],
                system="async_subagent",
                status="running",
            ))
        except Exception:
            pass  # registry integration is best-effort

        return sub_agent.id

    async def _run_sub_agent(self, sub_agent: AsyncSubAgent, timeout: float) -> None:
        """Run a sub-agent asynchronously."""
        sub_agent.status = AsyncSubAgentStatus.RUNNING
        sub_agent.started_at = datetime.now().isoformat()

        try:
            async with self._semaphore:
                if not self.agent_factory:
                    sub_agent.result = f"[No agent] Would process: {sub_agent.prompt[:100]}"
                    sub_agent.status = AsyncSubAgentStatus.COMPLETED
                    return

                agent = self.agent_factory()

                # Use async if available
                if hasattr(agent, "arun"):
                    result = await asyncio.wait_for(
                        agent.arun(sub_agent.prompt),
                        timeout=timeout,
                    )
                else:
                    # Fallback: run sync in thread pool
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, agent.run, sub_agent.prompt),
                        timeout=timeout,
                    )

                sub_agent.result = result
                sub_agent.status = AsyncSubAgentStatus.COMPLETED

                # Track metrics
                if hasattr(agent, "get_metrics_summary"):
                    metrics = agent.get_metrics_summary()
                    if metrics:
                        sub_agent.tool_calls = metrics.get("counters", {}).get("tool_calls", 0)
                        sub_agent.tokens_used = (
                            metrics.get("counters", {}).get("input_tokens", 0)
                            + metrics.get("counters", {}).get("output_tokens", 0)
                        )

        except TimeoutError:
            sub_agent.status = AsyncSubAgentStatus.FAILED
            sub_agent.error = f"Timeout after {timeout}s"
        except asyncio.CancelledError:
            sub_agent.status = AsyncSubAgentStatus.CANCELLED
            sub_agent.error = "Cancelled"
        except Exception as e:
            error_str = str(e).lower()
            # Provider doesn't support subagent (e.g. thinking/reasoning_effort conflict):
            # fall back to inline execution in the main agent
            if any(kw in error_str for kw in (
                "accessdenied", "invalidparameter",
                "thinking options", "reasoning_effort",
                "not supported", "unavailable",
            )):
                sub_agent.result = (
                    f"[Subagent unavailable — provider compatibility issue]\n"
                    f"Original error: {e}\n\n"
                    f"Task: {sub_agent.prompt[:200]}"
                )
                sub_agent.status = AsyncSubAgentStatus.DEGRADED
            else:
                sub_agent.status = AsyncSubAgentStatus.FAILED
                sub_agent.error = str(e)
        finally:
            sub_agent.completed_at = datetime.now().isoformat()

    async def wait(self, agent_id: str, timeout: float | None = None) -> str:
        """Wait for a specific sub-agent to complete.

        Args:
            agent_id: Sub-agent ID
            timeout: Timeout in seconds

        Returns:
            Result string
        """
        if agent_id not in self._agents:
            raise ValueError(f"Unknown sub-agent: {agent_id}")

        task = self._tasks.get(agent_id)
        if task:
            try:
                await asyncio.wait_for(task, timeout=timeout)
            except TimeoutError:
                return f"Timeout waiting for {agent_id}"

        agent = self._agents[agent_id]
        if agent.status == AsyncSubAgentStatus.COMPLETED:
            return agent.result or ""
        elif agent.status == AsyncSubAgentStatus.FAILED:
            return f"Error: {agent.error}"
        elif agent.status == AsyncSubAgentStatus.CANCELLED:
            return "Cancelled"
        else:
            return "Still running"

    async def wait_all(self, timeout: float | None = None) -> dict[str, str]:
        """Wait for all sub-agents to complete.

        Args:
            timeout: Timeout per sub-agent

        Returns:
            Dict mapping agent_id to result
        """
        results = {}
        for agent_id in self._agents:
            result = await self.wait(agent_id, timeout)
            results[agent_id] = result
        return results

    async def cancel(self, agent_id: str) -> bool:
        """Cancel a running sub-agent.

        Args:
            agent_id: Sub-agent ID

        Returns:
            True if cancelled
        """
        if agent_id not in self._agents:
            return False

        task = self._tasks.get(agent_id)
        if task and not task.done():
            task.cancel()
            self._agents[agent_id].status = AsyncSubAgentStatus.CANCELLED
            return True
        return False

    def get_status(self, agent_id: str | None = None) -> dict[str, Any]:
        """Get status of sub-agents.

        Args:
            agent_id: Optional specific agent ID

        Returns:
            Status dict
        """
        if agent_id:
            if agent_id not in self._agents:
                return {"error": "Unknown agent"}
            return self._agents[agent_id].to_dict()

        return {
            "total": len(self._agents),
            "pending": sum(1 for a in self._agents.values() if a.status == AsyncSubAgentStatus.PENDING),
            "running": sum(1 for a in self._agents.values() if a.status == AsyncSubAgentStatus.RUNNING),
            "completed": sum(1 for a in self._agents.values() if a.status == AsyncSubAgentStatus.COMPLETED),
            "failed": sum(1 for a in self._agents.values() if a.status == AsyncSubAgentStatus.FAILED),
            "cancelled": sum(1 for a in self._agents.values() if a.status == AsyncSubAgentStatus.CANCELLED),
        }

    def list_agents(self) -> list[dict[str, Any]]:
        """List all sub-agents.

        Returns:
            List of agent info dicts
        """
        return [agent.to_dict() for agent in self._agents.values()]

    async def run_parallel(
        self,
        prompts: list[str],
        timeout: float | None = None,
    ) -> dict[str, str]:
        """Run multiple prompts in parallel using asyncio.gather.

        Args:
            prompts: List of prompts
            timeout: Timeout per prompt

        Returns:
            Dict mapping prompt index to result
        """
        agent_ids = []
        for prompt in prompts:
            agent_id = await self.spawn(prompt, timeout)
            agent_ids.append(agent_id)

        # True parallel wait via asyncio.gather
        wait_tasks = [self.wait(aid, timeout) for aid in agent_ids]
        raw_results = await asyncio.gather(*wait_tasks, return_exceptions=True)

        results = {}
        for i, r in enumerate(raw_results):
            results[str(i)] = str(r) if isinstance(r, Exception) else r
        return results

    async def run_sequential(
        self,
        prompts: list[str],
        timeout: float | None = None,
    ) -> dict[str, str]:
        """Run multiple prompts sequentially.

        Args:
            prompts: List of prompts
            timeout: Timeout per prompt

        Returns:
            Dict mapping prompt index to result
        """
        results = {}
        carry = ""

        for i, prompt in enumerate(prompts):
            full_prompt = f"{prompt}\n\n[Previous result]\n{carry}" if carry else prompt
            agent_id = await self.spawn(full_prompt, timeout)
            result = await self.wait(agent_id, timeout)
            results[str(i)] = result
            carry = result

        return results
