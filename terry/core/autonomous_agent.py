"""Autonomous agent loop — background self-directed task execution.

Implements the full clone→analyze→fix→test→PR pipeline that runs
autonomously in the background without user interaction.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir


class AutonomousTask:
    """A self-contained task for the autonomous agent to execute."""

    def __init__(
        self,
        task_id: str,
        description: str,
        repo_url: str = "",
        branch: str = "main",
        task_type: str = "fix",  # fix, feature, refactor, review
    ):
        self.id = task_id
        self.description = description
        self.repo_url = repo_url
        self.branch = branch
        self.task_type = task_type
        self.status = "pending"  # pending → cloning → analyzing → fixing → testing → pr → done
        self.result: str | None = None
        self.error: str | None = None
        self.pr_url: str | None = None
        self.started_at: str | None = None
        self.completed_at: str | None = None
        self.log: list[str] = []

    def log_step(self, message: str) -> None:
        self.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "description": self.description,
            "task_type": self.task_type, "status": self.status,
            "result": self.result, "error": self.error,
            "pr_url": self.pr_url, "started_at": self.started_at,
            "completed_at": self.completed_at, "log": self.log,
        }


class AutonomousAgent:
    """Background agent that executes the full clone→test→fix→PR pipeline.

    Operates in a separate thread without blocking the main agent loop.
    Tasks are queued and executed sequentially.
    """

    STAGES = ["clone", "analyze", "fix", "test", "commit", "pr"]

    def __init__(
        self,
        agent_factory: Callable,
        workdir: Path | None = None,
        max_concurrent: int = 2,
        task_dir: Path | None = None,
    ):
        self.agent_factory = agent_factory
        self.workdir = workdir or Path.cwd()
        self.max_concurrent = max_concurrent
        self.task_dir = task_dir or get_terry_dir("autonomous_tasks")
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.queue: list[AutonomousTask] = []
        self.active: dict[str, AutonomousTask] = {}
        self.completed: list[AutonomousTask] = []
        self._running = False
        self._thread: threading.Thread | None = None

    def submit_task(
        self, description: str, repo_url: str = "",
        task_type: str = "fix",
    ) -> str:
        """Submit a task for autonomous execution. Returns task ID."""
        tid = f"auto_{int(time.time())}"
        task = AutonomousTask(tid, description, repo_url, task_type=task_type)
        self.queue.append(task)
        self._save_task(task)
        return tid

    def execute_task(self, task: AutonomousTask) -> AutonomousTask:
        """Execute the full pipeline for a single task."""
        task.status = "cloning"
        task.started_at = datetime.now().isoformat()
        task.log_step(f"Starting task: {task.description}")

        # Stage 1: Clone (if repo URL provided)
        work_dir = self.workdir
        if task.repo_url and task.repo_url.startswith(("http", "git@")):
            task.log_step(f"Cloning {task.repo_url}...")
            task.status = "cloning"
            try:
                work_dir = Path(tempfile.mkdtemp(prefix="terry_auto_"))
                subprocess.run(
                    ["git", "clone", task.repo_url, str(work_dir)],
                    capture_output=True, text=True, timeout=120, check=True,
                )
                task.log_step("Clone complete")
            except subprocess.CalledProcessError as e:
                task.status = "failed"
                task.error = f"Clone failed: {e.stderr}"
                task.completed_at = datetime.now().isoformat()
                return task

        agent = self.agent_factory()

        # Stage 2: Analyze
        task.status = "analyzing"
        task.log_step("Analyzing codebase...")
        try:
            analysis = agent.run(
                f"Analyze the codebase and identify issues related to: {task.description}. "
                f"List specific files and line numbers that need changes."
            )
            task.log_step(f"Analysis: {analysis[:200]}...")
        except Exception as e:
            task.log_step(f"Analysis failed: {e}")

        # Stage 3: Fix
        task.status = "fixing"
        task.log_step("Applying fixes...")
        try:
            fix_result = agent.run(
                f"Based on the analysis, apply the necessary fixes for: {task.description}. "
                f"Use write_file and edit_file tools to make the changes."
            )
            task.result = fix_result[:2000]
            task.log_step(f"Fix applied: {fix_result[:200]}...")
        except Exception as e:
            task.status = "failed"
            task.error = f"Fix failed: {e}"
            task.completed_at = datetime.now().isoformat()
            return task

        # Stage 4: Test
        task.status = "testing"
        task.log_step("Running tests...")
        try:
            test_result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-q"],
                cwd=work_dir,
                capture_output=True, text=True, timeout=120,
            )
            test_output = (test_result.stdout + test_result.stderr)[:2000]
            task.log_step(f"Tests: {test_output[:200]}")
            if test_result.returncode != 0:
                task.log_step("Tests failed — attempting fix...")
                # One retry
                fix_result = agent.run(
                    f"Tests failed with:\n{test_output}\n\nFix the failing tests."
                )
                task.log_step(f"Retry fix: {fix_result[:200]}...")
        except Exception as e:
            task.log_step(f"Test stage error: {e}")

        # Stage 5: Commit (if git repo)
        task.status = "committing"
        if self._is_git_repo(work_dir):
            try:
                subprocess.run(
                    ["git", "add", "-A"], cwd=work_dir,
                    capture_output=True, text=True, timeout=15,
                )
                subprocess.run(
                    ["git", "commit", "-m", f"auto: {task.description[:72]}"],
                    cwd=work_dir, capture_output=True, text=True, timeout=15,
                )
                task.log_step("Changes committed")
            except Exception as e:
                task.log_step(f"Commit failed: {e}")

        # Stage 6: PR (stub — needs GitHub token)
        task.status = "pr"
        task.log_step("PR creation stub — implement with GitHub token")
        # Future: use gh CLI or GitHub API to create PR

        task.status = "done"
        task.completed_at = datetime.now().isoformat()
        task.log_step("Task complete")
        return task

    def _is_git_repo(self, path: Path) -> bool:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path, capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False

    def start(self) -> None:
        """Start the autonomous agent in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """Background execution loop."""
        while self._running:
            # Process queue
            while self.queue and len(self.active) < self.max_concurrent:
                task = self.queue.pop(0)
                self.active[task.id] = task
                self.execute_task(task)
                self.completed.append(task)
                del self.active[task.id]
                self._save_task(task)

            time.sleep(5)

    def stop(self) -> None:
        self._running = False

    def get_status(self) -> dict[str, Any]:
        return {
            "queued": len(self.queue),
            "active": len(self.active),
            "completed": len(self.completed),
            "active_tasks": [
                {"id": t.id, "status": t.status, "description": t.description[:80]}
                for t in list(self.active.values())[:5]
            ],
        }

    def _save_task(self, task: AutonomousTask) -> None:
        tf = self.task_dir / f"{task.id}.json"
        tf.write_text(json.dumps(task.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def load_task_history(self) -> list[dict]:
        tasks = []
        for tf in sorted(self.task_dir.glob("auto_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                tasks.append(json.loads(tf.read_text(encoding="utf-8")))
            except Exception:
                pass
        return tasks[:50]


class SkillAutoCreator:
    """Automatically extracts patterns from successful conversations and creates SKILL.md files.

    Analyzes agent responses to identify reusable workflows, then generates
    structured SKILL.md files with triggers, descriptions, and instructions.
    """

    SKILL_TEMPLATE = """---
name: {name}
description: {description}
triggers:
{triggers}
---

# {title}

{instructions}

## Process

{process}

## Tools to Use

{tools}

## Guidelines

- Auto-generated from successful conversation pattern
- Review and refine before regular use
"""

    def __init__(
        self, skills_dir: Path | None = None, min_confidence: float = 0.6
    ):
        self.skills_dir = skills_dir or get_terry_dir("skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.min_confidence = min_confidence
        self._patterns: dict[str, int] = {}  # pattern signature → occurrence count

    def analyze_conversation(
        self, user_message: str, assistant_response: str,
    ) -> dict | None:
        """Analyze a conversation turn for reusable skill patterns.

        Returns skill suggestion dict or None if no pattern detected.
        """
        # Pattern detection heuristics
        patterns = []

        # Multi-step workflows
        step_markers = ["1.", "2.", "3.", "First", "Then", "Finally", "Step 1", "Step 2"]
        has_steps = sum(1 for m in step_markers if m in assistant_response)
        if has_steps >= 2:
            patterns.append("multi_step_workflow")

        # Code generation
        if "def " in assistant_response or "class " in assistant_response:
            patterns.append("code_generation")

        # Data analysis
        if any(w in user_message.lower() for w in ("analyze", "data", "csv", "json", "statistics")):
            patterns.append("data_analysis")

        # Bug fixing
        if any(w in user_message.lower() for w in ("fix", "bug", "error", "debug", "issue")):
            patterns.append("bug_fixing")

        # Documentation
        if any(w in user_message.lower() for w in ("document", "readme", "docstring", "explain")):
            patterns.append("documentation")

        if not patterns:
            return None

        # Track pattern frequency
        signature = "|".join(sorted(patterns))
        self._patterns[signature] = self._patterns.get(signature, 0) + 1

        # Only suggest if pattern seen multiple times
        if self._patterns[signature] < 2:
            return None

        # Generate skill suggestion
        name = self._generate_skill_name(patterns, user_message)
        description = f"Auto-generated skill: {', '.join(patterns)}"
        triggers = self._extract_triggers(user_message)

        return {
            "name": name,
            "description": description,
            "patterns": patterns,
            "triggers": triggers,
            "confidence": min(0.95, 0.5 + self._patterns[signature] * 0.1),
            "signature": signature,
        }

    def _generate_skill_name(self, patterns: list[str], user_message: str) -> str:
        """Generate a skill name from detected patterns."""
        primary = patterns[0]
        words = user_message.lower().split()[:5]
        key_words = [w for w in words if len(w) > 3 and w not in ("what", "this", "that", "with", "from")]
        if key_words:
            return f"auto-{primary.replace('_', '-')}-{'-'.join(key_words[:2])}"
        return f"auto-{primary.replace('_', '-')}"

    def _extract_triggers(self, user_message: str) -> list[str]:
        """Extract trigger phrases from user message."""
        words = user_message.lower().split()
        triggers = []
        for i in range(len(words)):
            for j in range(2, 6):
                if i + j <= len(words):
                    phrase = " ".join(words[i:i+j])
                    if len(phrase) > 8:
                        triggers.append(phrase)
                        if len(triggers) >= 3:
                            return triggers
        return triggers[:3] if triggers else [user_message[:50]]

    def create_skill(
        self, suggestion: dict, agent_response: str,
    ) -> Path | None:
        """Create a SKILL.md file from a pattern suggestion.

        Args:
            suggestion: Dict from analyze_conversation()
            agent_response: The assistant's response to use as skill body

        Returns:
            Path to created skill file, or None
        """
        if suggestion["confidence"] < self.min_confidence:
            return None

        name = suggestion["name"]
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        triggers_yaml = "\n".join(f"  - {t}" for t in suggestion["triggers"])

        # Extract process from response
        process = self._extract_process(agent_response)

        content = self.SKILL_TEMPLATE.format(
            name=name,
            description=suggestion["description"],
            triggers=triggers_yaml,
            title=name.replace("-", " ").title(),
            instructions=agent_response[:2000],
            process=process,
            tools="- Use appropriate tools based on the task\n- Always verify results",
        )

        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content, encoding="utf-8")

        # Mark as auto-generated
        meta_file = skill_dir / ".auto_generated"
        meta_file.write_text(
            json.dumps({
                "created_at": datetime.now().isoformat(),
                "signature": suggestion["signature"],
                "confidence": suggestion["confidence"],
            }, indent=2),
            encoding="utf-8",
        )

        return skill_file

    def _extract_process(self, response: str) -> str:
        """Extract process steps from response."""
        process_lines = []
        for line in response.split("\n"):
            line = line.strip()
            if any(line.startswith(f"{n}.") for n in range(1, 10)) or \
               any(line.startswith(p) for p in ("- First", "- Then", "- Finally", "1.", "2.")):
                process_lines.append(line)
        if process_lines:
            return "\n".join(process_lines[:10])
        return "1. Analyze the request\n2. Execute the solution\n3. Verify the result"

    def list_suggested_skills(self) -> list[dict]:
        """List auto-generated skills waiting for review."""
        skills = []
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            meta_file = skill_dir / ".auto_generated"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    skills.append({
                        "name": skill_dir.name,
                        "confidence": meta.get("confidence", 0),
                        "created_at": meta.get("created_at", ""),
                    })
                except Exception:
                    pass
        return sorted(skills, key=lambda s: s["confidence"], reverse=True)

    def approve_skill(self, name: str) -> bool:
        """Approve an auto-generated skill (removes .auto_generated marker)."""
        meta_file = self.skills_dir / name / ".auto_generated"
        if meta_file.exists():
            meta_file.unlink()
            return True
        return False

    def get_pattern_stats(self) -> dict:
        return {
            "patterns_detected": len(self._patterns),
            "total_occurrences": sum(self._patterns.values()),
            "patterns": sorted(
                self._patterns.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }
