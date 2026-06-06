"""Terry Harness — unified orchestration layer for multi-agent execution.

The Harness is the execution framework that the LLM uses to compose
and run complex multi-step workflows. It unifies:
  - DynamicWorkflowEngine (6 orchestration patterns)
  - SubAgentManager (threaded sub-agents with worktree isolation)
  - Orchestrator (pipeline/parallel/map-reduce)
  - Token budget tracking
  - Checkpoint/resume

As a Tool, the Harness lets the Agent programmatically spawn sub-agents,
orchestrate them in patterns, and manage resources — all from within
the normal conversation flow.

Usage as a tool:
    Agent detects a complex task
        → calls harness.execute(pattern="fan-out-merge", goals=[...])
        → Harness spawns sub-agents, coordinates, merges results
        → Returns consolidated response to Agent
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class HarnessPattern(StrEnum):
    """Orchestration patterns supported by the Harness."""
    SEQUENTIAL = "sequential"           # A → B → C
    PARALLEL = "parallel"               # A ‖ B ‖ C
    FAN_OUT_MERGE = "fan-out-merge"     # Split → parallel → combine
    ADVERSARIAL_VERIFY = "adversarial-verify"  # Generate → verify → fix
    TOURNAMENT = "tournament"           # N solutions → compare → best wins
    CLASSIFY_EXECUTE = "classify-execute"  # Classify → route → execute
    LOOP_UNTIL_DONE = "loop-until-done" # Iterate until quality threshold
    GENERATE_FILTER = "generate-filter" # Generate → score → deduplicate


class HarnessTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class HarnessTask:
    """A unit of work in the Harness."""
    id: str = field(default_factory=lambda: f"ht_{uuid.uuid4().hex[:8]}")
    description: str = ""
    prompt: str = ""
    pattern: HarnessPattern = HarnessPattern.SEQUENTIAL
    depends_on: list[str] = field(default_factory=list)
    status: HarnessTaskStatus = HarnessTaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    tool_calls: int = 0
    tokens_used: int = 0
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "pattern": self.pattern.value, "status": self.status.value,
            "result": self.result, "error": self.error,
            "tool_calls": self.tool_calls, "tokens_used": self.tokens_used,
        }


class HarnessEngine:
    """Unified orchestration engine — the Terry Harness.

    Coordinates sub-agents, workflows, and resources through a single API.
    Designed to be exposed as a Tool so the LLM can programmatically
    compose and execute complex multi-step tasks.

    Architecture:
        HarnessEngine
        ├── DynamicWorkflowEngine (6 patterns)
        ├── SubAgentManager (threaded agents + worktree)
        ├── BudgetTracker (token + time limits)
        └── CheckpointManager (save/resume)
    """

    CHECKPOINT_DIR = Path.home() / ".terry" / "harness"

    def __init__(
        self,
        agent_factory: Callable | None = None,
        max_concurrent: int = 5,
        token_budget: int | None = None,
        default_timeout: float = 300.0,
    ):
        self.agent_factory = agent_factory
        self.max_concurrent = max_concurrent
        self.token_budget = token_budget
        self.default_timeout = default_timeout
        self.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

        self.tasks: dict[str, HarnessTask] = {}
        self.results: dict[str, str] = {}
        self._running = False
        self._tokens_spent = 0
        self._start_time: float = 0

    # ── Public API ─────────────────────────────────────────────────

    def create_task(
        self,
        description: str,
        prompt: str = "",
        pattern: str = "sequential",
        depends_on: list[str] | None = None,
    ) -> str:
        """Create a task in the Harness. Returns task ID."""
        task = HarnessTask(
            description=description,
            prompt=prompt,
            pattern=HarnessPattern(pattern),
            depends_on=depends_on or [],
        )
        self.tasks[task.id] = task
        return task.id

    def execute(
        self,
        pattern: str = "sequential",
        prompts: list[str] | None = None,
        goals: list[str] | None = None,
        context: dict | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute tasks using the specified orchestration pattern.

        This is the main entry point — called by the Agent as a tool.

        Args:
            pattern: One of sequential, parallel, fan-out-merge,
                     adversarial-verify, tournament, classify-execute,
                     loop-until-done, generate-filter
            prompts: List of task prompts (for sequential/parallel)
            goals: High-level goals (for fan-out/merge/tournament)
            context: Additional context variables
            timeout: Per-task timeout in seconds

        Returns:
            Dict with results, metadata, and task summaries
        """
        timeout = timeout or self.default_timeout
        self._start_time = time.time()
        self.results = {}

        pattern_enum = HarnessPattern(pattern)
        prompts = prompts or []
        goals = goals or []

        if pattern_enum == HarnessPattern.SEQUENTIAL:
            result = self._run_sequential(prompts, timeout)
        elif pattern_enum == HarnessPattern.PARALLEL:
            result = self._run_parallel(prompts, timeout)
        elif pattern_enum == HarnessPattern.FAN_OUT_MERGE:
            result = self._run_fan_out_merge(goals or prompts, timeout)
        elif pattern_enum == HarnessPattern.ADVERSARIAL_VERIFY:
            result = self._run_adversarial_verify(goals, timeout)
        elif pattern_enum == HarnessPattern.TOURNAMENT:
            result = self._run_tournament(goals or prompts, timeout)
        elif pattern_enum == HarnessPattern.CLASSIFY_EXECUTE:
            result = self._run_classify_execute(prompts, timeout)
        elif pattern_enum == HarnessPattern.LOOP_UNTIL_DONE:
            result = self._run_loop_until_done(goals, timeout)
        elif pattern_enum == HarnessPattern.GENERATE_FILTER:
            result = self._run_generate_filter(goals or prompts, timeout)
        else:
            result = {"error": f"Unknown pattern: {pattern}"}

        duration = time.time() - self._start_time
        result["_metadata"] = {
            "pattern": pattern,
            "tasks_total": len(self.tasks),
            "duration_seconds": round(duration, 2),
            "tokens_spent": self._tokens_spent,
            "budget_remaining": (
                self.token_budget - self._tokens_spent
                if self.token_budget else "unlimited"
            ),
        }
        return result

    # ── Pattern Implementations ────────────────────────────────────

    def _run_sequential(self, prompts: list[str], timeout: float) -> dict:
        """Execute prompts one after another, feeding output forward."""
        results = {}
        carry = ""
        for i, prompt in enumerate(prompts):
            full_prompt = f"{prompt}\n\n[Previous result]\n{carry}" if carry else prompt
            tid = self.create_task(f"step_{i+1}", full_prompt, "sequential")
            self.tasks[tid].status = HarnessTaskStatus.RUNNING
            try:
                output = self._run_single(full_prompt, timeout)
                carry = output
                results[tid] = output
                self.tasks[tid].status = HarnessTaskStatus.COMPLETED
                self.tasks[tid].result = output[:1000]
            except Exception as e:
                self.tasks[tid].status = HarnessTaskStatus.FAILED
                self.tasks[tid].error = str(e)
                results[tid] = f"Error: {e}"
                break
        return {"results": results, "steps_completed": len(results)}

    def _run_parallel(self, prompts: list[str], timeout: float) -> dict:
        """Execute all prompts concurrently."""
        results: dict[str, str] = {}
        threads = []
        lock = threading.Lock()

        def worker(prompt: str, tid: str):
            try:
                output = self._run_single(prompt, timeout)
                with lock:
                    results[tid] = output
            except Exception as e:
                with lock:
                    results[tid] = f"Error: {e}"

        for prompt in prompts:
            tid = self.create_task(prompt[:60], prompt, "parallel")
            self.tasks[tid].status = HarnessTaskStatus.RUNNING
            t = threading.Thread(target=worker, args=(prompt, tid), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout)

        for tid, result in results.items():
            if tid in self.tasks:
                self.tasks[tid].status = (
                    HarnessTaskStatus.COMPLETED if not result.startswith("Error")
                    else HarnessTaskStatus.FAILED
                )
                self.tasks[tid].result = result[:1000]

        return {"results": results, "parallel_tasks": len(prompts)}

    def _run_fan_out_merge(self, items: list[str], timeout: float) -> dict:
        """Split goal into sub-tasks, execute in parallel, merge results."""
        # Fan-out
        fan_results = self._run_parallel(items, timeout)

        # Merge
        if self.agent_factory:
            all_results = "\n---\n".join(
                f"Result {i}: {r}" for i, r in enumerate(fan_results["results"].values())
            )
            agent = self.agent_factory()
            merged = agent.run(
                f"Combine and deduplicate these results into one cohesive answer:\n\n{all_results}"
            )
            return {"merged": merged, "fan_out_results": fan_results["results"]}
        return {"fan_out_results": fan_results["results"]}

    def _run_adversarial_verify(self, goals: list[str], timeout: float) -> dict:
        """Generate → Verify → Fix loop."""
        if not goals or not self.agent_factory:
            return {"error": "Need goals and agent_factory"}

        agent = self.agent_factory()
        goal = goals[0]

        # Generate
        solution = agent.run(goal)
        # Verify
        verdict = agent.run(
            f"Critically review this solution and identify any issues. "
            f"Rate as PASS or FAIL:\n\n{solution[:3000]}"
        )
        # Fix if needed
        if "FAIL" in verdict.upper():
            fixed = agent.run(
                f"Fix the issues identified:\n\nIssues: {verdict[:1000]}\n\n"
                f"Original: {solution[:2000]}"
            )
            return {"status": "fixed", "original": solution[:2000], "fix": fixed[:2000], "verdict": verdict[:1000]}
        return {"status": "passed", "solution": solution[:2000], "verdict": verdict[:1000]}

    def _run_tournament(self, entries: list[str], timeout: float) -> dict:
        """Run all solutions, pairwise compare, return best."""
        if len(entries) < 2:
            return {"error": "Need at least 2 entries for tournament"}

        # Run all contestants
        parallel_result = self._run_parallel(entries, timeout)
        solutions = list(parallel_result["results"].values())

        # Pairwise comparison
        if self.agent_factory:
            scores = [0] * len(solutions)
            agent = self.agent_factory()
            for i in range(len(solutions)):
                for j in range(i + 1, len(solutions)):
                    choice = agent.run(
                        f"Compare these two solutions. Reply with A or B:\n\n"
                        f"A: {solutions[i][:500]}\n\nB: {solutions[j][:500]}"
                    ).strip().upper()
                    if "A" in choice:
                        scores[i] += 1
                    elif "B" in choice:
                        scores[j] += 1

            winner_idx = scores.index(max(scores))
            return {
                "winner_index": winner_idx,
                "winner": solutions[winner_idx][:2000],
                "scores": scores,
            }
        return {"solutions": solutions}

    def _run_classify_execute(self, prompts: list[str], timeout: float) -> dict:
        """Classify the task type, then route to handler."""
        if not prompts or not self.agent_factory:
            return {"error": "Need prompts and agent_factory"}

        agent = self.agent_factory()
        task_type = agent.run(
            f"Classify this task into ONE word: {prompts[0]}"
        ).strip().lower()
        result = agent.run(
            f"[Task type: {task_type}] {prompts[0]}"
        )
        return {"task_type": task_type, "result": result[:3000]}

    def _run_loop_until_done(self, goals: list[str], timeout: float) -> dict:
        """Iterate until quality threshold met."""
        if not goals or not self.agent_factory:
            return {"error": "Need goals and agent_factory"}

        agent = self.agent_factory()
        goal = goals[0]
        current = ""
        for iteration in range(5):
            prompt = f"{goal}\n\nPrevious attempt:\n{current}" if current else goal
            current = agent.run(prompt)
            score_resp = agent.run(
                f"Rate this solution from 0.0 to 1.0. Reply with just the number:\n\n{current[:2000]}"
            )
            try:
                score = float(score_resp.strip()[:10])
                if score >= 0.8:
                    return {"iterations": iteration + 1, "score": score, "result": current[:3000]}
            except ValueError:
                pass
        return {"iterations": 5, "result": current[:3000], "status": "max_iterations"}

    def _run_generate_filter(self, items: list[str], timeout: float) -> dict:
        """Generate ideas, score, deduplicate, return top-N."""
        if not self.agent_factory:
            return {"error": "Need agent_factory"}

        agent = self.agent_factory()
        all_ideas = []
        for prompt in items:
            resp = agent.run(f"Generate 3 distinct ideas for: {prompt}")
            all_ideas.extend(
                line.strip("- 123456789. ")
                for line in resp.split("\n")
                if line.strip() and not line.startswith("#")
            )

        # Deduplicate
        seen = set()
        unique = []
        for idea in all_ideas:
            key = idea.lower()[:80]
            if key not in seen:
                seen.add(key)
                unique.append(idea)

        return {"ideas": unique[:20], "total_generated": len(all_ideas), "unique": len(unique)}

    # ── Core execution ─────────────────────────────────────────────

    def _run_single(self, prompt: str, timeout: float) -> str:
        """Execute a single prompt through the agent."""
        if not self.agent_factory:
            return f"[No agent] Would process: {prompt[:100]}"

        agent = self.agent_factory()
        result = agent.run(prompt)
        # Track token spend
        metrics = agent.get_metrics_summary()
        if metrics:
            counters = metrics.get("counters", {})
            self._tokens_spent += counters.get("input_tokens", 0)
            self._tokens_spent += counters.get("output_tokens", 0)
        return result

    # ── Checkpoint / Resume ─────────────────────────────────────────

    def save_checkpoint(self) -> Path:
        """Save current Harness state to disk."""
        cp_file = self.CHECKPOINT_DIR / f"harness_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "results": self.results,
            "tokens_spent": self._tokens_spent,
            "token_budget": self.token_budget,
        }
        cp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return cp_file

    def resume(self, checkpoint_path: Path) -> dict | None:
        """Resume from a saved checkpoint."""
        if not checkpoint_path.exists():
            return None
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        self._tokens_spent = data.get("tokens_spent", 0)
        self.results = data.get("results", {})

        # Re-run incomplete tasks
        incomplete = [
            t for t in data.get("tasks", {}).values()
            if t.get("status") in ("pending", "running", "failed")
        ]
        prompts = [t.get("prompt", t.get("description", "")) for t in incomplete]
        if prompts:
            return self._run_sequential(prompts, self.default_timeout)
        return {"status": "all_complete", "restored_tasks": len(data.get("tasks", {}))}

    def get_status(self) -> dict[str, Any]:
        """Get current Harness status."""
        return {
            "tasks": len(self.tasks),
            "pending": sum(1 for t in self.tasks.values() if t.status == HarnessTaskStatus.PENDING),
            "running": sum(1 for t in self.tasks.values() if t.status == HarnessTaskStatus.RUNNING),
            "completed": sum(1 for t in self.tasks.values() if t.status == HarnessTaskStatus.COMPLETED),
            "failed": sum(1 for t in self.tasks.values() if t.status == HarnessTaskStatus.FAILED),
            "tokens_spent": self._tokens_spent,
            "budget": self.token_budget or "unlimited",
        }


# ── Harness Tool: exposed to the Agent ─────────────────────────

# (registered via terry/tools/harness_tool.py, imported by discover_tools())
