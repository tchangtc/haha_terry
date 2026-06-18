"""Ultrareview — multi-agent adversarial code review.

4 independent review dimensions, each reviewed by a dedicated sub-agent.
Each finding is adversarially verified with 3-vote majority before reporting.
Auto-fix loop: fix → re-review until all dimensions pass or max iterations.

Usage:
    reviewer = Ultrareview(agent_factory=lambda: agent)
    result = reviewer.review(code, file_path="src/main.py")
    if not result.passed:
        result = reviewer.auto_fix(code, result)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

REVIEW_DIMENSIONS: dict[str, str] = {
    "correctness": (
        "Analyze for correctness: logic errors, race conditions, edge cases, "
        "null safety, type mismatches, off-by-one errors, boundary conditions."
    ),
    "security": (
        "Analyze for security: injection flaws, XSS, CSRF, path traversal, "
        "hardcoded secrets, insufficient input validation, privilege escalation."
    ),
    "performance": (
        "Analyze for performance: O(n^2)+ algorithms, unnecessary I/O, "
        "memory leaks, cache-unfriendly patterns, redundant computation."
    ),
    "maintainability": (
        "Analyze for maintainability: poor naming, excessive duplication, "
        "high coupling, low cohesion, missing documentation, magic numbers."
    ),
}


@dataclass
class UltrareviewFinding:
    """A single finding from a review dimension."""
    dimension: str = ""
    severity: str = "minor"  # critical | major | minor
    location: str = ""
    description: str = ""
    suggestion: str = ""
    votes: int = 0
    passed: bool = False  # True if 2/3 majority


@dataclass
class UltrareviewResult:
    """Complete ultrareview pass result."""
    findings: list[UltrareviewFinding] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    passed: bool = False
    fixed_code: str = ""


class Ultrareview:
    """Multi-dimension adversarial code reviewer with auto-fix loop."""

    def __init__(
        self,
        agent_factory: Callable | None = None,
        max_iterations: int = 3,
    ):
        self.agent_factory = agent_factory
        self.max_iterations = max_iterations

    def review(self, code: str, file_path: str = "") -> UltrareviewResult:
        """Run full multi-dimension review.

        Each dimension gets an independent reviewer agent. Findings are
        adversarially verified with 3 votes (2/3 majority required).
        """
        if not self.agent_factory:
            return UltrareviewResult(passed=True)

        result = UltrareviewResult()
        all_findings: list[UltrareviewFinding] = []

        for dim, instruction in REVIEW_DIMENSIONS.items():
            try:
                agent = self.agent_factory()
                prompt = (
                    f"Review the following code for {dim}.\n\n"
                    f"{instruction}\n\n"
                    f"File: {file_path or '<inline>'}\n\n"
                    f"```\n{code[:6000]}\n```\n\n"
                    f"Output a JSON array of findings: "
                    f'[{{"severity":"major","location":"...","description":"...","suggestion":"..."}}]'
                )
                response = agent.run(prompt)
                findings = self._parse_findings(dim, response)

                for finding in findings:
                    finding.votes = self._adversarial_verify(code, finding)
                    finding.passed = finding.votes >= 2  # 2/3 majority
                all_findings.extend(findings)

                scores = {f.severity: 0 for f in findings}
                for f in findings:
                    scores[f.severity] = scores.get(f.severity, 0) + 1
                passed_count = sum(1 for f in findings if f.passed)
                result.scores[dim] = passed_count / len(findings) if findings else 1.0
            except Exception as e:
                logger.warning("Ultrareview dimension %s failed: %s", dim, e)
                result.scores[dim] = 0.0

        result.findings = all_findings
        result.passed = all(s >= 0.8 for s in result.scores.values()) if result.scores else True
        return result

    def auto_fix(self, code: str, result: UltrareviewResult) -> UltrareviewResult:
        """Fix findings, re-review, repeat until passed or max iterations."""
        current_code = code
        for iteration in range(self.max_iterations):
            if result.passed:
                break

            critical = [f for f in result.findings if f.severity == "critical" and not f.passed]
            major = [f for f in result.findings if f.severity == "major" and not f.passed]
            if not critical and not major:
                result.passed = True
                break

            agent = self.agent_factory() if self.agent_factory else None
            if not agent:
                break

            fix_prompt = "Fix the following issues:\n\n"
            for f in (critical + major)[:10]:
                fix_prompt += (
                    f"- [{f.severity}] {f.dimension}: {f.description}\n"
                    f"  Suggestion: {f.suggestion}\n"
                )
            fix_prompt += f"\nCode:\n```\n{current_code[:4000]}\n```\n\nReturn ONLY the fixed code."
            current_code = agent.run(fix_prompt)

            result = self.review(current_code)
            result.iterations = iteration + 1
            result.fixed_code = current_code

        result.fixed_code = current_code
        return result

    def _parse_findings(self, dimension: str, response: str) -> list[UltrareviewFinding]:
        """Parse JSON findings from agent response with fallback heuristics."""
        findings: list[UltrareviewFinding] = []
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    findings.append(UltrareviewFinding(
                        dimension=dimension,
                        severity=item.get("severity", "minor"),
                        location=item.get("location", ""),
                        description=item.get("description", ""),
                        suggestion=item.get("suggestion", ""),
                    ))
        except (json.JSONDecodeError, TypeError):
            for line in response.split("\n"):
                if any(kw in line.lower() for kw in ("vulnerability", "bug", "error", "issue", "problem")):
                    findings.append(UltrareviewFinding(
                        dimension=dimension,
                        severity="minor",
                        description=line.strip()[:200],
                    ))
        return findings

    def _adversarial_verify(
        self, code: str, finding: UltrareviewFinding,
    ) -> int:
        """Run 3 independent verifiers. Returns vote count (0-3)."""
        votes = 0
        for _ in range(3):
            agent = self.agent_factory() if self.agent_factory else None
            if not agent:
                break
            prompt = (
                f"Verify this finding. Reply ONLY 'CONFIRMED' or 'REJECTED'.\n\n"
                f"Finding: [{finding.severity}] {finding.dimension}: {finding.description}\n"
                f"Suggestion: {finding.suggestion}\n\n"
                f"Code:\n```\n{code[:3000]}\n```"
            )
            response = agent.run(prompt).strip().upper()
            if "CONFIRMED" in response:
                votes += 1
        return votes
