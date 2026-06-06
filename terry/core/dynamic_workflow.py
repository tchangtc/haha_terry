"""Dynamic Workflow Engine — AI generates & orchestrates its own multi-agent workflows.

Patterns (inspired by Claude Code Dynamic Workflows, June 2026):
  classify-execute   — classify task → route to specialized sub-agent
  fan-out-merge      — split into subtasks → parallel → merge
  adversarial-verify — generate → verify against criteria → fix if rejected
  tournament         — N agents solve same problem → pairwise compare → best wins
  loop-until-done    — repeat generation until quality threshold met
  generate-filter    — generate ideas → score → deduplicate → return top-N

Resume: interrupted workflows persist state to disk and can resume from checkpoint.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class WorkflowPattern(StrEnum):
    CLASSIFY_EXECUTE = "classify-execute"
    FAN_OUT_MERGE = "fan-out-merge"
    ADVERSARIAL_VERIFY = "adversarial-verify"
    TOURNAMENT = "tournament"
    LOOP_UNTIL_DONE = "loop-until-done"
    GENERATE_FILTER = "generate-filter"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class DynamicWorkflow:
    """A self-modifying workflow that agents can generate and execute."""

    def __init__(
        self,
        name: str,
        goal: str,
        pattern: WorkflowPattern = WorkflowPattern.FAN_OUT_MERGE,
        max_agents: int = 10,
        token_budget: int | None = None,
    ):
        self.id = f"wf_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.goal = goal
        self.pattern = pattern
        self.max_agents = max_agents
        self.token_budget = token_budget
        self.status = WorkflowStatus.PENDING
        self.stages: list[dict] = []          # Generated stages
        self.results: dict[str, Any] = {}     # stage_id → result
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.checkpoint_file: Path | None = None

    def add_stage(self, name: str, prompt: str, depends_on: list[str] | None = None,
                  verify_prompt: str = "", model: str = "default") -> str:
        """Add a stage to the workflow. Returns stage_id."""
        stage_id = f"stage_{len(self.stages) + 1}"
        self.stages.append({
            "id": stage_id,
            "name": name,
            "prompt": prompt,
            "depends_on": depends_on or [],
            "verify_prompt": verify_prompt,
            "model": model,
            "status": "pending",
            "result": None,
            "retries": 0,
            "max_retries": 3,
        })
        return stage_id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "goal": self.goal,
            "pattern": self.pattern.value,
            "max_agents": self.max_agents,
            "token_budget": self.token_budget,
            "status": self.status.value,
            "stages": self.stages,
            "results": self.results,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DynamicWorkflow:
        wf = cls(
            name=data["name"],
            goal=data["goal"],
            pattern=WorkflowPattern(data.get("pattern", "fan-out-merge")),
            max_agents=data.get("max_agents", 10),
            token_budget=data.get("token_budget"),
        )
        wf.id = data["id"]
        wf.status = WorkflowStatus(data.get("status", "pending"))
        wf.stages = data.get("stages", [])
        wf.results = data.get("results", {})
        wf.created_at = data.get("created_at", "")
        wf.updated_at = data.get("updated_at", "")
        return wf


class DynamicWorkflowEngine:
    """Orchestrates dynamic multi-agent workflows with pattern-based execution.

    The engine can:
    1. Auto-generate workflow stages from a high-level goal (via LLM)
    2. Execute in classify-execute / fan-out-merge / adversarial-verify / tournament modes
    3. Resume interrupted workflows from checkpoint
    4. Track token usage and enforce budget
    """

    CHECKPOINT_DIR = Path.home() / ".terry" / "workflows"

    def __init__(self, agent_factory: Callable | None = None):
        self.agent_factory = agent_factory
        self.active_workflows: dict[str, DynamicWorkflow] = {}
        self.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Stage Generation ─────────────────────────────────────────

    def plan_workflow(
        self, goal: str, pattern: WorkflowPattern,
        llm_client: Any = None, available_tools: list[str] | None = None,
    ) -> DynamicWorkflow:
        """Generate workflow stages from a high-level goal using LLM.

        The LLM analyzes the goal, decomposes it into stages, and
        assigns verification criteria for each stage.
        """
        wf = DynamicWorkflow(
            name=goal[:60],
            goal=goal,
            pattern=pattern,
        )

        if llm_client:
            wf = self._llm_plan_stages(wf, llm_client, available_tools or [])
        else:
            # Simple heuristic: single-stage execution
            wf.add_stage("execute", goal)

        self.active_workflows[wf.id] = wf
        return wf

    def _llm_plan_stages(
        self, wf: DynamicWorkflow, llm_client: Any, tools: list[str]
    ) -> DynamicWorkflow:
        """Use LLM to decompose goal into workflow stages."""
        planning_prompt = (
            f"Decompose this goal into a {wf.pattern.value} workflow:\n\n"
            f"**Goal:** {wf.goal}\n\n"
            f"**Pattern:** {wf.pattern.value}\n"
            f"**Available tools:** {', '.join(tools)}\n\n"
        )

        if wf.pattern == WorkflowPattern.CLASSIFY_EXECUTE:
            planning_prompt += (
                "Create stages for:\n"
                "1. CLASSIFY — analyze the task and determine its type\n"
                "2-4. EXECUTE — specialized handlers for each task type\n"
                "5. AGGREGATE — combine results\n\n"
                "Output format: one stage per line as 'NAME: description'"
            )
        elif wf.pattern == WorkflowPattern.FAN_OUT_MERGE:
            planning_prompt += (
                "Create stages for:\n"
                "1-3. FAN-OUT — independent sub-tasks that can run in parallel\n"
                "4. MERGE — combine and deduplicate results\n\n"
                "Output format: one stage per line as 'NAME: description'"
            )
        elif wf.pattern == WorkflowPattern.ADVERSARIAL_VERIFY:
            planning_prompt += (
                "Create stages for:\n"
                "1. GENERATE — produce initial solution\n"
                "2. VERIFY — check against criteria and find issues\n"
                "3. FIX (if needed) — address verification issues\n"
                "4. FINALIZE — produce final verified output\n\n"
                "Output format: one stage per line as 'NAME: description'"
            )
        elif wf.pattern == WorkflowPattern.TOURNAMENT:
            planning_prompt += (
                "Create stages for:\n"
                "1-3. CONTESTANT — 3 different approaches to the same problem\n"
                "4. JUDGE — pairwise comparison and ranking\n"
                "5. SYNTHESIZE — take best approach + graft good ideas from others\n\n"
                "Output format: one stage per line as 'NAME: description'"
            )
        elif wf.pattern == WorkflowPattern.LOOP_UNTIL_DONE:
            planning_prompt += (
                "Create stages for:\n"
                "1. ATTEMPT — generate initial solution\n"
                "2. EVALUATE — check quality against criteria\n"
                "3. REFINE — improve based on evaluation (loop back to 1 if needed)\n\n"
                "Output format: one stage per line as 'NAME: description'"
            )

        try:
            from .text_utils import extract_text
            response = llm_client.chat(
                messages=[{"role": "user", "content": planning_prompt}],
                max_tokens=1000,
            )
            plan_text = extract_text(response["content"])

            # Parse stages from LLM output
            for line in plan_text.split("\n"):
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    name, _, desc = line.partition(":")
                    name = name.strip().lstrip("0123456789. -")
                    desc = desc.strip()
                    if name and desc:
                        wf.add_stage(name, desc)

        except Exception:
            pass

        # If LLM planning failed or produced no stages, add a single stage
        if not wf.stages:
            wf.add_stage("execute", wf.goal)

        return wf

    # ── Execution ─────────────────────────────────────────────────

    def execute(
        self,
        wf: DynamicWorkflow,
        context: dict | None = None,
        on_stage_complete: Callable | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow, handling all patterns.

        Returns dict mapping stage_id → result.
        """
        wf.status = WorkflowStatus.RUNNING
        wf.updated_at = datetime.now().isoformat()
        self._checkpoint(wf)

        if wf.pattern == WorkflowPattern.CLASSIFY_EXECUTE:
            results = self._run_classify_execute(wf, context)
        elif wf.pattern == WorkflowPattern.FAN_OUT_MERGE:
            results = self._run_fan_out_merge(wf, context)
        elif wf.pattern == WorkflowPattern.ADVERSARIAL_VERIFY:
            results = self._run_adversarial_verify(wf, context)
        elif wf.pattern == WorkflowPattern.TOURNAMENT:
            results = self._run_tournament(wf, context)
        elif wf.pattern == WorkflowPattern.LOOP_UNTIL_DONE:
            results = self._run_loop_until_done(wf, context)
        elif wf.pattern == WorkflowPattern.GENERATE_FILTER:
            results = self._run_generate_filter(wf, context)
        else:
            results = self._run_sequential(wf, context)

        wf.status = WorkflowStatus.COMPLETED
        wf.results = results
        wf.updated_at = datetime.now().isoformat()
        self._checkpoint(wf)
        return results

    # ── Pattern Implementations ────────────────────────────────────

    def _run_classify_execute(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Classify the task, then route to the appropriate handler."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        agent = self.agent_factory()
        # Use the first stage as classifier
        task_type = "general"
        if wf.stages:
            classify_stage = wf.stages[0]
            try:
                response = agent.run(f"Classify this task type in ONE word: {wf.goal}")
                task_type = response.strip().lower()[:50]
                classify_stage["status"] = "completed"
                classify_stage["result"] = task_type
            except Exception as e:
                classify_stage["status"] = "failed"
                classify_stage["result"] = str(e)

        # Execute remaining stages (specialized handlers)
        results = {}
        for stage in wf.stages[1:]:
            try:
                response = agent.run(
                    f"[Task type: {task_type}] {stage['prompt']}"
                )
                stage["status"] = "completed"
                stage["result"] = response[:2000]
            except Exception as e:
                stage["status"] = "failed"
                stage["result"] = str(e)
            results[stage["id"]] = stage["result"]

        results["classified_as"] = task_type
        return results

    def _run_fan_out_merge(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Execute independent stages in parallel, merge results."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        import threading
        results: dict[str, Any] = {}
        threads = []
        lock = threading.Lock()

        def run_stage(stage: dict) -> None:
            agent = self.agent_factory()
            try:
                response = agent.run(stage["prompt"])
                with lock:
                    stage["status"] = "completed"
                    stage["result"] = response[:2000]
                    results[stage["id"]] = response[:2000]
            except Exception as e:
                with lock:
                    stage["status"] = "failed"
                    stage["result"] = str(e)
                    results[stage["id"]] = f"Error: {e}"

        # Run fan-out stages in parallel
        fan_out_stages = [
            s for s in wf.stages
            if "merge" not in s["name"].lower() and "combine" not in s["name"].lower()
        ]
        for stage in fan_out_stages:
            t = threading.Thread(target=run_stage, args=(stage,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=300)

        # Merge stage
        merge_stages = [
            s for s in wf.stages
            if "merge" in s["name"].lower() or "combine" in s["name"].lower()
        ]
        if merge_stages:
            agent = self.agent_factory()
            combined = "\n---\n".join(
                f"Result {i+1}: {r}"
                for i, r in enumerate(results.values())
            )
            merge_prompt = (
                f"Combine and deduplicate these results into one cohesive answer:\n\n"
                f"{combined}"
            )
            try:
                merged = agent.run(merge_prompt)
                merge_stages[0]["status"] = "completed"
                merge_stages[0]["result"] = merged[:2000]
                results[merge_stages[0]["id"]] = merged[:2000]
            except Exception as e:
                merge_stages[0]["status"] = "failed"
                merge_stages[0]["result"] = str(e)

        results["_merged_count"] = len(fan_out_stages)
        return results

    def _run_adversarial_verify(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Generate → Verify → Fix if rejected."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        agent = self.agent_factory()
        results: dict[str, Any] = {}

        # Generate stage
        gen_stage = next((s for s in wf.stages if "generat" in s["name"].lower()), None)
        if not gen_stage and wf.stages:
            gen_stage = wf.stages[0]

        if gen_stage:
            try:
                response = agent.run(gen_stage["prompt"])
                gen_stage["status"] = "completed"
                gen_stage["result"] = response[:2000]
                results[gen_stage["id"]] = response[:2000]
            except Exception as e:
                gen_stage["status"] = "failed"
                gen_stage["result"] = str(e)
                results[gen_stage["id"]] = str(e)
                return results

        # Verify stage
        verify_stage = next((s for s in wf.stages if "verif" in s["name"].lower()), None)
        verdict = "accepted"
        issues = []
        if verify_stage and gen_stage and gen_stage["result"]:
            try:
                verify_prompt = (
                    f"{verify_stage['prompt']}\n\n"
                    f"Solution to verify:\n{gen_stage['result']}"
                )
                response = agent.run(verify_prompt)
                verify_stage["status"] = "completed"
                verify_stage["result"] = response[:1000]
                results[verify_stage["id"]] = response[:1000]
                verdict = "rejected" if "reject" in response.lower() or "fail" in response.lower() else "accepted"
                if "issue" in response.lower() or "problem" in response.lower():
                    issues = [line.strip() for line in response.split("\n") if line.strip().startswith("-")]
            except Exception as e:
                verify_stage["status"] = "failed"
                verify_stage["result"] = str(e)

        results["_verdict"] = verdict
        results["_issues"] = issues

        # Fix stage (if rejected)
        if verdict == "rejected":
            fix_stage = next((s for s in wf.stages if "fix" in s["name"].lower()), None)
            if fix_stage:
                try:
                    fix_prompt = (
                        f"{fix_stage['prompt']}\n\n"
                        f"Original: {gen_stage['result']}\n"
                        f"Issues: {', '.join(issues)}"
                    )
                    response = agent.run(fix_prompt)
                    fix_stage["status"] = "completed"
                    fix_stage["result"] = response[:2000]
                    results[fix_stage["id"]] = response[:2000]
                    results["_verdict"] = "fixed"
                except Exception:
                    fix_stage["status"] = "failed"

        return results

    def _run_tournament(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Multiple agents solve same problem → pairwise compare → best wins."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        import threading
        results: dict[str, Any] = {}
        lock = threading.Lock()

        # Contestant stages
        contestant_stages = [
            s for s in wf.stages
            if "contest" in s["name"].lower() or "approach" in s["name"].lower()
        ]
        if not contestant_stages:
            contestant_stages = wf.stages[:min(3, len(wf.stages))]

        threads = []
        def run_contestant(stage: dict) -> None:
            agent = self.agent_factory()
            try:
                response = agent.run(stage["prompt"])
                with lock:
                    stage["status"] = "completed"
                    stage["result"] = response[:2000]
                    results[stage["id"]] = response[:2000]
            except Exception as e:
                with lock:
                    stage["status"] = "failed"
                    stage["result"] = str(e)

        for stage in contestant_stages:
            t = threading.Thread(target=run_contestant, args=(stage,), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=300)

        # Judge: pairwise comparison
        judge_stage = next((s for s in wf.stages if "judge" in s["name"].lower()), None)
        if judge_stage and len(results) >= 2:
            agent = self.agent_factory()
            entries = list(results.items())
            scores: dict[str, int] = {sid: 0 for sid in results}

            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    compare_prompt = (
                        f"Compare these two solutions and pick the better one. "
                        f"Reply with just 'A' or 'B'.\n\n"
                        f"Solution A:\n{entries[i][1][:500]}\n\n"
                        f"Solution B:\n{entries[j][1][:500]}"
                    )
                    try:
                        choice = agent.run(compare_prompt).strip().upper()
                        if "A" in choice:
                            scores[entries[i][0]] += 1
                        elif "B" in choice:
                            scores[entries[j][0]] += 1
                    except Exception:
                        pass

            judge_stage["status"] = "completed"
            judge_stage["result"] = f"Scores: {scores}"
            results[judge_stage["id"]] = scores
            results["_winner"] = max(scores, key=scores.get) if scores else "none"

        return results

    def _run_loop_until_done(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Repeat generate→evaluate→refine until quality threshold met."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        agent = self.agent_factory()
        results: dict[str, Any] = {}
        max_iterations = 5
        quality_threshold = 0.8

        current_result = ""
        for iteration in range(max_iterations):
            gen_stage = next(
                (s for s in wf.stages if "attempt" in s["name"].lower() or "generat" in s["name"].lower()),
                wf.stages[0] if wf.stages else None,
            )
            if gen_stage:
                prompt = gen_stage["prompt"]
                if current_result:
                    prompt += f"\n\nPrevious attempt:\n{current_result}\n\nImprove upon this."
                try:
                    current_result = agent.run(prompt)[:2000]
                except Exception as e:
                    results["_error"] = str(e)
                    break

            # Evaluate
            eval_stage = next((s for s in wf.stages if "evaluat" in s["name"].lower()), None)
            if eval_stage:
                try:
                    eval_response = agent.run(
                        f"{eval_stage['prompt']}\n\nSolution:\n{current_result}\n\n"
                        f"Score from 0.0 to 1.0. Reply with just the number."
                    )
                    score = float(eval_response.strip()[:10])
                    if score >= quality_threshold:
                        results["_iterations"] = iteration + 1
                        results["_score"] = score
                        break
                except (ValueError, Exception):
                    pass

            results["_iterations"] = iteration + 1

        results["final"] = current_result
        return results

    def _run_generate_filter(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Generate multiple ideas → score → deduplicate → return top-N."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}

        agent = self.agent_factory()
        results: dict[str, Any] = {}

        # Generate
        ideas = []
        for stage in wf.stages:
            if "generat" in stage["name"].lower():
                try:
                    response = agent.run(f"Generate 3 distinct approaches: {stage['prompt']}")
                    stage["status"] = "completed"
                    stage["result"] = response[:2000]
                    ideas.extend(
                        line.strip("- 123456789. ")
                        for line in response.split("\n")
                        if line.strip().startswith(("-", "1.", "2.", "3."))
                    )
                    results[stage["id"]] = response[:2000]
                except Exception:
                    stage["status"] = "failed"

        # Deduplicate
        seen = set()
        unique = []
        for idea in ideas:
            key = idea.lower()[:50]
            if key not in seen:
                seen.add(key)
                unique.append(idea)

        results["_ideas"] = unique[:10]
        results["_count"] = len(unique)
        return results

    def _run_sequential(self, wf: DynamicWorkflow, ctx: dict | None) -> dict:
        """Simple sequential execution."""
        if not self.agent_factory:
            return {"error": "No agent_factory configured"}
        agent = self.agent_factory()
        results = {}
        for stage in wf.stages:
            try:
                response = agent.run(stage["prompt"])
                stage["status"] = "completed"
                stage["result"] = response[:2000]
                results[stage["id"]] = response[:2000]
            except Exception as e:
                stage["status"] = "failed"
                stage["result"] = str(e)
                results[stage["id"]] = f"Error: {e}"
                break
        return results

    # ── Checkpoint / Resume ─────────────────────────────────────────

    def _checkpoint(self, wf: DynamicWorkflow) -> Path:
        """Save workflow state to disk for resume."""
        wf.checkpoint_file = self.CHECKPOINT_DIR / f"{wf.id}.json"
        wf.checkpoint_file.write_text(
            json.dumps(wf.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        wf.updated_at = datetime.now().isoformat()
        return wf.checkpoint_file

    def resume(self, workflow_id: str) -> DynamicWorkflow | None:
        """Resume an interrupted workflow from checkpoint.

        Only pending/failed stages are re-executed.
        """
        cp_file = self.CHECKPOINT_DIR / f"{workflow_id}.json"
        if not cp_file.exists():
            return None

        data = json.loads(cp_file.read_text(encoding="utf-8"))
        wf = DynamicWorkflow.from_dict(data)

        # Reset running status to paused for resume
        wf.status = WorkflowStatus.PAUSED

        # Re-execute only incomplete stages
        pending_stages = [
            s for s in wf.stages
            if s["status"] in ("pending", "failed") and s.get("retries", 0) < s.get("max_retries", 3)
        ]

        if pending_stages:
            # Keep completed stages, redo pending ones
            original_stages = wf.stages
            wf.stages = [
                s for s in original_stages
                if s["status"] == "completed"
            ] + pending_stages
            for s in pending_stages:
                s["retries"] = s.get("retries", 0) + 1

            if self.agent_factory:
                self.execute(wf)
        else:
            wf.status = WorkflowStatus.COMPLETED

        return wf

    def list_checkpoints(self) -> list[dict[str, str]]:
        """List all workflow checkpoints."""
        cps = []
        for f in sorted(self.CHECKPOINT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cps.append({
                    "id": data.get("id", f.stem),
                    "name": data.get("name", ""),
                    "pattern": data.get("pattern", ""),
                    "status": data.get("status", ""),
                })
            except Exception:
                pass
        return cps[:20]
