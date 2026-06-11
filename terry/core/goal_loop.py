"""Goal-driven autonomous loop — generate, evaluate, refine until done.

Uses a dual-model architecture:
  - Main agent (expensive) for generation/refinement
  - Evaluator model (cheap) for scoring progress

Pattern: parse_criteria → generate → evaluate → refine → ... → done

Usage:
    loop = GoalLoop(agent, evaluator_model)
    result = loop.run("Refactor login module to use async patterns")
    print(result.summary())
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


EVALUATOR_PROMPT = """You are a goal evaluator. Determine if a goal has been met.

Goal: {goal}

Current state / result:
{result}

Success criteria:
{criteria}

Evaluate the current state against the goal and all success criteria.
Be critical and specific. Reply with a JSON object (no markdown, no code fences):
{{"met": bool, "score": 0.0-1.0, "feedback": "specific improvement suggestions", "missing": ["list", "of", "missing", "elements"]}}

Score guide:
- 1.0 = goal fully met, all criteria satisfied, no improvements needed
- 0.8-0.99 = mostly met, minor gaps remain
- 0.5-0.79 = partially met, significant gaps
- 0.0-0.49 = not met, major rework needed
"""


@dataclass
class GoalResult:
    """Result of a goal-driven loop execution."""

    met: bool = False
    iterations: int = 0
    final_score: float = 0.0
    feedback: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    final_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise for API/JSON output."""
        return {
            "met": self.met,
            "iterations": self.iterations,
            "final_score": self.final_score,
            "feedback": self.feedback,
            "final_output": self.final_output[:500],
            "history": self.history[-5:],
        }

    def summary(self) -> str:
        """One-line summary of the result."""
        status = "achieved" if self.met else "not achieved"
        return (
            f"Goal {status} after {self.iterations} iteration(s) "
            f"(score: {self.final_score:.2f})"
        )


class GoalLoop:
    """Iterative goal-driven loop that generates, evaluates, and refines.

    The main agent does the work. A separate evaluator model (typically
    cheaper) scores progress. The loop refines until the quality threshold
    is met or max iterations are reached.
    """

    DEFAULT_MAX_ITERATIONS = 10
    DEFAULT_QUALITY_THRESHOLD = 0.85

    def __init__(
        self,
        agent: Any,
        evaluator_model: Any | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
        on_progress: Any | None = None,
    ):
        """Initialize the goal loop.

        Args:
            agent: Main Agent instance used for generation and refinement.
            evaluator_model: LLMClient for evaluation. If None, uses agent.llm.
            max_iterations: Maximum refinement iterations before giving up.
            quality_threshold: Minimum score (0.0–1.0) to consider goal met.
            on_progress: Optional callback(event: str, data: dict) for UI updates.
        """
        self.agent = agent
        self.evaluator_model = evaluator_model or agent.llm
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.on_progress = on_progress

    def run(self, goal: str) -> GoalResult:
        """Execute the goal-driven loop.

        Args:
            goal: Natural language description of the goal.

        Returns:
            GoalResult with outcome, score, iteration history, and final output.
        """
        result = GoalResult()

        # Step 1: Parse goal into success criteria
        criteria = self._parse_criteria(goal)
        logger.info("Goal loop starting: goal=%s criteria=%s", goal[:80], criteria[:120])

        current_output = ""
        for iteration in range(1, self.max_iterations + 1):
            logger.info("Goal loop iteration %d/%d", iteration, self.max_iterations)

            if self.on_progress:
                self.on_progress("goal_iteration", {
                    "iteration": iteration,
                    "max_iterations": self.max_iterations,
                })

            # a. Generate or refine using the main agent
            if iteration == 1:
                prompt = self._build_generation_prompt(goal, criteria)
            else:
                prompt = self._build_refinement_prompt(goal, criteria, current_output, eval_result)

            try:
                current_output = self.agent.run(prompt)
            except Exception as e:
                logger.error("Goal loop generation failed at iteration %d: %s", iteration, e)
                result.final_output = current_output or f"Error: {e}"
                result.final_score = 0.0
                result.feedback = str(e)
                break

            # b. Evaluate using the evaluator model
            try:
                eval_result = self._evaluate(goal, criteria, current_output)
            except Exception as e:
                logger.error("Goal loop evaluation failed at iteration %d: %s", iteration, e)
                eval_result = {
                    "met": False, "score": 0.5,
                    "feedback": f"Evaluation error: {e}", "missing": [],
                }

            score = float(eval_result.get("score", 0.0))
            met = bool(eval_result.get("met", False))
            feedback = str(eval_result.get("feedback", ""))

            # Record history
            result.history.append({
                "iteration": iteration,
                "score": score,
                "met": met,
                "feedback": feedback[:200],
            })

            if self.on_progress:
                self.on_progress("goal_evaluation", {
                    "iteration": iteration,
                    "score": score,
                    "met": met,
                    "feedback": feedback[:200],
                })

            result.final_score = score
            result.final_output = current_output
            result.feedback = feedback

            # c. Check threshold
            if met or score >= self.quality_threshold:
                result.met = True
                result.iterations = iteration
                logger.info("Goal achieved at iteration %d (score: %.2f)", iteration, score)
                break

        else:
            # Max iterations reached without meeting goal
            result.iterations = self.max_iterations
            logger.info(
                "Goal loop reached max iterations (%d) without meeting threshold (score: %.2f)",
                self.max_iterations, result.final_score,
            )

        if result.iterations == 0:
            result.iterations = max(1, len(result.history))

        if self.on_progress:
            self.on_progress("goal_done", result.to_dict())

        return result

    def _parse_criteria(self, goal: str) -> str:
        """Use LLM to decompose the goal into explicit, measurable success criteria.

        Returns a bullet-point string.
        """
        prompt = (
            "Given this goal, list 3–5 specific, measurable success criteria "
            "that must be met. Return as bullet points:\n\n"
            f"Goal: {goal}"
        )
        try:
            response = self.evaluator_model.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            from .text_utils import extract_text
            criteria = str(extract_text(response.get("content", "")))
            return criteria[:1000]
        except Exception as e:
            logger.warning("Criteria parsing failed, using goal as-is: %s", e)
            return goal

    def _build_generation_prompt(self, goal: str, criteria: str) -> str:
        """Build the initial generation prompt."""
        return (
            f"## Goal\n{goal}\n\n"
            f"## Success Criteria\n{criteria}\n\n"
            "Work through this goal systematically. Use available tools "
            "(write_file, edit_file, bash, grep, etc.) to achieve every criterion. "
            "Focus on making concrete, verifiable progress. "
            "When you've addressed all criteria, report what you accomplished."
        )

    def _build_refinement_prompt(
        self,
        goal: str,
        criteria: str,
        previous_output: str,
        eval_result: dict[str, Any],
    ) -> str:
        """Build the refinement prompt incorporating feedback from the prior attempt."""
        feedback = eval_result.get("feedback", "Improve the solution.")
        missing = eval_result.get("missing", [])
        missing_str = "\n".join(f"- {m}" for m in missing) if missing else "Review all criteria"

        return (
            f"## Goal\n{goal}\n\n"
            f"## Success Criteria\n{criteria}\n\n"
            f"## Feedback from Previous Attempt\n{feedback}\n\n"
            f"## Still Missing\n{missing_str}\n\n"
            f"## Previous Output (for reference)\n{previous_output[:2000]}\n\n"
            "Refine and improve the above based on the feedback. "
            "Address each missing element. Aim to fully meet all success criteria."
        )

    def _evaluate(self, goal: str, criteria: str, output: str) -> dict[str, Any]:
        """Evaluate current output against the goal using the evaluator model.

        Returns dict with keys: met, score, feedback, missing.
        """
        prompt_content = EVALUATOR_PROMPT.format(
            goal=goal,
            result=output[:4000],
            criteria=criteria,
        )
        response = self.evaluator_model.chat(
            messages=[{"role": "user", "content": prompt_content}],
            max_tokens=500,
        )
        from .text_utils import extract_text
        text = str(extract_text(response.get("content", "")))

        # Strip markdown code fences if the model wrapped its JSON
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            if "```" in text:
                text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            result: dict[str, Any] = json.loads(text)
            return {
                "met": bool(result.get("met", False)),
                "score": float(result.get("score", 0.0)),
                "feedback": str(result.get("feedback", "")),
                "missing": result.get("missing", []),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Failed to parse evaluator JSON response: %s", e)
            return {
                "met": False,
                "score": 0.0,
                "feedback": text[:500],
                "missing": [],
            }
