"""Subagent system - spawn parallel agents with optional worktree isolation.

Worktree isolation: When the working directory is a git repo,
sub-agents get their own git worktree under .terry/worktrees/.
This prevents file conflicts and provides filesystem-level safety.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from ..hooks import hook_registry
from ..tools import ToolRegistry
from .config import TerryConfig
from .llm import LLMClient
from .text_utils import extract_text


class SubAgent:
    """A lightweight agent that runs in a separate thread with hook support."""

    MAX_ITERATIONS = 20
    MAX_TOOL_OUTPUT_LENGTH = 100_000  # ~25K tokens

    def __init__(
        self,
        task_id: str,
        prompt: str,
        config: TerryConfig,
        workdir: Path,
        tools: ToolRegistry,
        on_complete: Callable[[str, str], None] | None = None,
        hooks=None,
    ):
        self.task_id = task_id
        self.prompt = prompt
        self.config = config
        self.workdir = workdir
        self.tools = tools
        self.on_complete = on_complete
        self.llm = LLMClient(config.model)
        self.hooks = hooks or hook_registry

        self.thread: threading.Thread | None = None
        self.result_queue: queue.Queue[str] = queue.Queue()
        self.status = "pending"  # pending, running, completed, failed
        self.tool_call_count = 0

    def start(self) -> None:
        """Start the subagent in a background thread."""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        """Run the subagent task."""
        self.status = "running"

        try:
            # Build messages
            messages = [{"role": "user", "content": self.prompt}]

            # Agent loop with tool call budget
            for _ in range(self.MAX_ITERATIONS):
                response = self.llm.chat(
                    messages=messages,
                    system=f"You are a subagent working on: {self.prompt}",
                    tools=self.tools.get_definitions(),
                    max_tokens=self.config.model.max_tokens,
                )

                messages.append({"role": "assistant", "content": response["content"]})

                # Check if done
                if response["stop_reason"] != "tool_use":
                    result = extract_text(response["content"])
                    self.status = "completed"
                    self.result_queue.put(result)

                    if self.on_complete:
                        self.on_complete(self.task_id, result)
                    return

                # Execute tools with hook pipeline
                results = []
                for block in response["content"]:
                    if not hasattr(block, "type") or block.type != "tool_use":
                        continue

                    # === Hook: PreToolUse (permission check) ===
                    blocked = self.hooks.trigger("PreToolUse", block)
                    if blocked:
                        output = str(blocked)
                    else:
                        # Execute tool with output truncation
                        try:
                            output = self.tools.execute(block.name, **block.input)
                            output_str = str(output)
                            if len(output_str) > self.MAX_TOOL_OUTPUT_LENGTH:
                                output_str = (
                                    output_str[:self.MAX_TOOL_OUTPUT_LENGTH]
                                    + "\n\n... (output truncated)"
                                )
                            output = output_str
                        except Exception as e:
                            output = f"Error: {e}"

                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })

                    self.tool_call_count += 1
                    self.hooks.trigger("PostToolUse", block, output)

                messages.append({"role": "user", "content": results})

            # Max iterations reached
            self.status = "failed"
            self.result_queue.put("Error: Maximum tool calls exceeded")

        except Exception as e:
            error_str = str(e).lower()
            # Graceful degradation: flag provider incompatibility instead of failing
            if any(kw in error_str for kw in (
                "accessdenied", "invalidparameter",
                "thinking options", "reasoning_effort",
                "not supported", "unavailable",
            )):
                self.status = "degraded"
                self.result_queue.put(
                    f"[Subagent unavailable — compatibility issue]\n{e}\n\nTask: {self.prompt[:200]}"
                )
            else:
                self.status = "failed"
                self.result_queue.put(f"Error: {e}")

    def wait(self, timeout: float | None = None) -> str:
        """Wait for the subagent to complete.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            Result text

        Raises:
            TimeoutError: If timeout exceeded
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"Subagent {self.task_id} did not complete within {timeout}s")

    def get_status(self) -> str:
        """Get current status."""
        return self.status


# ── Worktree utilities ────────────────────────────────────────────

def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _create_worktree(base_dir: Path, task_id: str) -> Path | None:
    """Create a git worktree for isolated sub-agent execution.

    Returns the worktree path, or None if creation failed.
    """
    if not _is_git_repo(base_dir):
        return None

    worktree_root = base_dir / ".terry" / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)

    branch_name = f"terry-subagent-{task_id}"
    worktree_path = worktree_root / task_id

    try:
        # Create worktree on a new orphan branch (no history)
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path)],
            cwd=base_dir, capture_output=True, text=True, timeout=30, check=True,
        )
        # Checkout a clean branch
        subprocess.run(
            ["git", "checkout", "--orphan", branch_name],
            cwd=worktree_path, capture_output=True, text=True, timeout=10, check=True,
        )
        # Remove all tracked files for clean state
        subprocess.run(
            ["git", "rm", "-rf", "--quiet", "."],
            cwd=worktree_path, capture_output=True, text=True, timeout=10,
        )
        return worktree_path
    except subprocess.CalledProcessError:
        return None


def _remove_worktree(base_dir: Path, worktree_path: Path) -> None:
    """Remove a git worktree and prune the branch."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=base_dir, capture_output=True, text=True, timeout=15,
        )
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=base_dir, capture_output=True, text=True, timeout=10,
        )
    except Exception:
        # Best-effort cleanup — try rm -rf fallback
        try:
            shutil.rmtree(worktree_path, ignore_errors=True)
        except Exception:
            pass


# ── Orchestrator ───────────────────────────────────────────────────

class Orchestrator:
    """Coordinates multiple subagents with pipeline, parallel, and map-reduce patterns."""

    def __init__(self, manager: SubAgentManager):
        self.manager = manager

    def pipeline(
        self, prompt: str, stages: list[dict], timeout: float = 300
    ) -> dict[str, str]:
        """Execute stages sequentially, passing results forward.

        Each stage receives the previous stage's output.
        """
        results = {}
        current_input = prompt

        for stage in stages:
            task_id = self.manager.spawn(
                f"{stage.get('description', '')}\n\nInput:\n{current_input}"
            )
            try:
                output = self.manager.wait(task_id, timeout=timeout)
                results[stage.get("name", task_id)] = output
                current_input = output
            except TimeoutError:
                results[stage.get("name", task_id)] = "Error: Timeout"
                break

        return results

    def parallel(
        self, tasks: list[dict], timeout: float = 300
    ) -> dict[str, str]:
        """Execute multiple tasks in parallel.

        Each task is a dict with 'name' and 'prompt' keys.
        """
        task_ids = {}
        for task in tasks:
            tid = self.manager.spawn(task["prompt"])
            task_ids[tid] = task.get("name", tid)

        return self.manager.wait_all(timeout=timeout)

    def map_reduce(
        self,
        items: list[str],
        map_prompt: str,
        reduce_prompt: str = "Combine and summarize the following results:\n{results}",
        timeout: float = 300,
    ) -> str:
        """Map: apply map_prompt to each item in parallel.
        Reduce: combine all results with reduce_prompt.
        """
        # Map phase
        tasks = [
            {"name": f"map_{i}", "prompt": map_prompt.replace("{item}", item)}
            for i, item in enumerate(items)
        ]
        map_results = self.parallel(tasks, timeout=timeout)

        # Reduce phase
        combined = "\n---\n".join(
            f"Item {i}: {r}" for i, r in enumerate(map_results.values())
        )
        reduce_task = {"name": "reduce", "prompt": reduce_prompt.replace("{results}", combined)}
        reduce_results = self.parallel([reduce_task], timeout=timeout)

        return list(reduce_results.values())[0] if reduce_results else ""


# ── SubAgentManager ────────────────────────────────────────────────

class SubAgentManager:
    """Manages multiple subagents with optional worktree isolation."""

    def __init__(
        self,
        config: TerryConfig,
        workdir: Path,
        tools: ToolRegistry,
        use_worktree: bool = True,
    ):
        self.config = config
        self.workdir = workdir
        self.tools = tools
        self.use_worktree = use_worktree and _is_git_repo(workdir)
        self.agents: dict[str, SubAgent] = {}
        self._worktrees: dict[str, Path] = {}
        self._counter = 0

    def spawn(
        self,
        prompt: str,
        on_complete: Callable[[str, str], None] | None = None,
        isolated: bool = True,
    ) -> str:
        """Spawn a new subagent.

        Args:
            prompt: Task prompt
            on_complete: Callback when agent completes (task_id, result)
            isolated: Use worktree isolation if available

        Returns:
            Task ID
        """
        self._counter += 1
        task_id = f"task_{self._counter}"

        # Create isolated worktree
        sub_workdir = self.workdir
        if isolated and self.use_worktree:
            wt_path = _create_worktree(self.workdir, task_id)
            if wt_path:
                sub_workdir = wt_path
                self._worktrees[task_id] = wt_path

        # Wrap on_complete to clean up worktree
        def _cleanup_callback(tid: str, result: str) -> None:
            if tid in self._worktrees:
                _remove_worktree(self.workdir, self._worktrees[tid])
                del self._worktrees[tid]
            if on_complete:
                on_complete(tid, result)

        agent = SubAgent(
            task_id=task_id,
            prompt=prompt,
            config=self.config,
            workdir=sub_workdir,
            tools=self.tools,
            on_complete=_cleanup_callback,
        )

        self.agents[task_id] = agent
        agent.start()
        return task_id

    def wait(self, task_id: str, timeout: float | None = None) -> str:
        """Wait for a specific task to complete.

        Args:
            task_id: Task ID
            timeout: Maximum wait time

        Returns:
            Result text
        """
        agent = self.agents.get(task_id)
        if not agent:
            raise ValueError(f"Unknown task: {task_id}")

        return agent.wait(timeout=timeout)

    def wait_all(self, timeout: float | None = None) -> dict[str, str]:
        """Wait for all tasks to complete.

        Args:
            timeout: Maximum wait time per task

        Returns:
            Dictionary of task_id -> result
        """
        results = {}
        for task_id, agent in self.agents.items():
            try:
                results[task_id] = agent.wait(timeout=timeout)
            except TimeoutError:
                results[task_id] = "Error: Timeout"

        return results

    def get_status(self, task_id: str) -> str:
        """Get status of a specific task.

        Args:
            task_id: Task ID

        Returns:
            Status string
        """
        agent = self.agents.get(task_id)
        return agent.get_status() if agent else "unknown"

    def list_tasks(self) -> list[dict[str, str]]:
        """List all tasks and their status.

        Returns:
            List of task info dictionaries
        """
        return [
            {
                "task_id": task_id,
                "status": agent.get_status(),
                "prompt": agent.prompt[:100],
            }
            for task_id, agent in self.agents.items()
        ]
