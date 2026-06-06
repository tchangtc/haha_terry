"""Plan-first execution mode - research before acting."""

from __future__ import annotations

from typing import Any


class Planner:
    """Generates structured plans before execution.

    Uses a dedicated LLM call with low temperature to produce a
    step-by-step plan that the user can review and approve before
    the agent executes it.
    """

    def __init__(self, llm_client: Any = None):
        """Initialize planner.

        Args:
            llm_client: LLM client for plan generation (uses agent's LLM)
        """
        self.llm = llm_client

    def create_plan(
        self,
        user_input: str,
        available_tools: list[str],
        workdir: str = ".",
    ) -> dict[str, Any]:
        """Generate a structured execution plan.

        Args:
            user_input: User's request
            available_tools: List of available tool names
            workdir: Working directory context

        Returns:
            Plan dictionary with rationale, steps, and tools needed
        """
        if not self.llm:
            return self._create_simple_plan(user_input, available_tools)

        prompt = self._build_planning_prompt(user_input, available_tools, workdir)

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are a planning expert. Your job is to create clear, "
                    "actionable plans. Be specific about which tools to use and "
                    "in what order. Focus on safety and efficiency."
                ),
                max_tokens=2000,
            )

            from .text_utils import extract_text
            plan_text = extract_text(response["content"])

            # Parse the plan text into structured format
            return self._parse_plan(plan_text, user_input, available_tools)

        except Exception:
            return self._create_simple_plan(user_input, available_tools)

    def _build_planning_prompt(
        self,
        user_input: str,
        available_tools: list[str],
        workdir: str,
    ) -> str:
        """Build the planning prompt."""
        return (
            f"Create a detailed execution plan for the following request:\n\n"
            f"**Request:** {user_input}\n\n"
            f"**Context:**\n"
            f"- Working directory: {workdir}\n"
            f"- Available tools: {', '.join(available_tools)}\n\n"
            f"**Instructions:**\n"
            f"1. First, list any RESEARCH steps (read-only exploration)\n"
            f"2. Then, list IMPLEMENTATION steps in order\n"
            f"3. For each step, specify which tool to use and why\n"
            f"4. Flag any steps that are DESTRUCTIVE (write/edit/bash)\n"
            f"5. Include a VERIFICATION step to confirm changes\n\n"
            f"Output your plan in this format:\n"
            f"```\n"
            f"## Plan\n"
            f"### Rationale\n"
            f"[Why this approach]\n\n"
            f"### Research Phase\n"
            f"1. [Tool: tool_name] - description\n\n"
            f"### Implementation Phase\n"
            f"1. [Tool: tool_name] [DESTRUCTIVE] - description\n\n"
            f"### Verification\n"
            f"1. [Tool: tool_name] - description\n"
            f"```"
        )

    def _parse_plan(
        self,
        plan_text: str,
        user_input: str,
        available_tools: list[str],
    ) -> dict[str, Any]:
        """Parse LLM-generated plan into structured format."""
        steps = []
        current_phase = "unknown"

        for line in plan_text.split("\n"):
            line = line.strip()
            if "### Research" in line:
                current_phase = "research"
            elif "### Implementation" in line:
                current_phase = "implementation"
            elif "### Verification" in line:
                current_phase = "verification"
            elif line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                is_destructive = "[DESTRUCTIVE]" in line
                tool_name = "unknown"
                for tool in available_tools:
                    if tool in line.lower():
                        tool_name = tool
                        break
                steps.append({
                    "phase": current_phase,
                    "description": line,
                    "destructive": is_destructive,
                    "tool": tool_name,
                })

        return {
            "rationale": self._extract_rationale(plan_text),
            "steps": steps,
            "research_count": sum(1 for s in steps if s["phase"] == "research"),
            "implementation_count": sum(1 for s in steps if s["phase"] == "implementation"),
            "verification_count": sum(1 for s in steps if s["phase"] == "verification"),
            "has_destructive": any(s["destructive"] for s in steps),
            "raw_plan": plan_text,
        }

    def _extract_rationale(self, plan_text: str) -> str:
        """Extract rationale from plan text."""
        in_rationale = False
        lines = []
        for line in plan_text.split("\n"):
            if "### Rationale" in line:
                in_rationale = True
                continue
            if in_rationale:
                if line.startswith("###"):
                    break
                if line.strip():
                    lines.append(line.strip())
        return " ".join(lines) if lines else "No rationale provided"

    def _create_simple_plan(
        self,
        user_input: str,
        available_tools: list[str],
    ) -> dict[str, Any]:
        """Create a simple plan without LLM (fallback)."""
        return {
            "rationale": "Simple sequential execution plan (LLM unavailable)",
            "steps": [
                {
                    "phase": "implementation",
                    "description": f"Execute: {user_input}",
                    "destructive": False,
                    "tool": "auto",
                }
            ],
            "research_count": 0,
            "implementation_count": 1,
            "verification_count": 0,
            "has_destructive": False,
            "raw_plan": f"# Plan\n\nExecute the user request directly: {user_input}",
        }

    def validate_plan(self, plan: dict[str, Any]) -> list[str]:
        """Validate a plan and return list of issues."""
        issues = []
        steps = plan.get("steps", [])

        if not steps:
            issues.append("Plan has no steps")
            return issues

        # Check for destructive steps without prior research
        has_research = any(s["phase"] == "research" for s in steps)
        has_destructive = plan.get("has_destructive", False)
        if has_destructive and not has_research:
            issues.append(
                "Plan has destructive steps but no research phase. "
                "Consider adding exploration steps first."
            )

        # Check step count
        if len(steps) > 20:
            issues.append(f"Plan has {len(steps)} steps — consider breaking into smaller tasks")

        return issues

    def format_plan(self, plan: dict[str, Any]) -> str:
        """Format plan as markdown for display."""
        parts = [
            "# Execution Plan\n",
            f"**Rationale:** {plan.get('rationale', 'N/A')}\n",
            f"**Summary:** {plan.get('research_count', 0)} research, "
            f"{plan.get('implementation_count', 0)} implementation, "
            f"{plan.get('verification_count', 0)} verification steps\n",
            "\n## Steps\n",
        ]

        current_phase = None
        for step in plan.get("steps", []):
            phase = step.get("phase", "unknown")
            if phase != current_phase:
                current_phase = phase
                parts.append(f"\n### {phase.title()} Phase\n")

            destructive_marker = " ⚠️ DESTRUCTIVE" if step.get("destructive") else ""
            parts.append(f"- {step['description']}{destructive_marker}\n")

        # Add issues if any
        issues = self.validate_plan(plan)
        if issues:
            parts.append("\n## ⚠️ Issues\n")
            for issue in issues:
                parts.append(f"- {issue}\n")

        return "".join(parts)
