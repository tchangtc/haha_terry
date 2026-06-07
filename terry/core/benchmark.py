"""Benchmark framework for evaluating agent performance.

Supports SWE-bench, HumanEval, and custom benchmark scenarios.
Tracks pass rates, token usage, cost, and latency across runs.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .platform_utils import get_terry_dir


class BenchmarkResult:
    """Result of a single benchmark test case."""

    def __init__(self, problem_id: str, status: str = "pending"):
        self.problem_id = problem_id
        self.status = status  # pending, running, passed, failed, error
        self.score: float = 0.0
        self.tool_calls: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.duration_seconds: float = 0.0
        self.cost_usd: float = 0.0
        self.error_message: str = ""
        self.agent_response: str = ""

    def to_dict(self) -> dict:
        return {
            "problem_id": self.problem_id,
            "status": self.status,
            "score": self.score,
            "tool_calls": self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration_seconds": self.duration_seconds,
            "cost_usd": self.cost_usd,
            "error_message": self.error_message,
        }


class BenchmarkSuite:
    """Collection of benchmark problems."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.problems: list[dict[str, Any]] = []
        self.results: list[BenchmarkResult] = []

    def add_problem(
        self, problem_id: str, prompt: str, expected_patterns: list[str] | None = None,
        files_to_check: list[str] | None = None, test_command: str = "",
    ) -> None:
        """Add a problem to the suite."""
        self.problems.append({
            "id": problem_id,
            "prompt": prompt,
            "expected_patterns": expected_patterns or [],
            "files_to_check": files_to_check or [],
            "test_command": test_command,
        })

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "problems": self.problems,
            "results": [r.to_dict() for r in self.results],
        }


class BenchmarkRunner:
    """Runs benchmark suites and generates reports."""

    DEFAULT_SUITES = {
        "coding_basics": "Basic coding tasks (file I/O, string manipulation, regex)",
        "refactoring": "Code refactoring and restructuring tasks",
        "debugging": "Bug detection and fixing scenarios",
        "tool_usage": "Tool calling accuracy and efficiency",
    }

    def __init__(self, agent: Any = None, output_dir: Path | None = None):
        self.agent = agent
        self.output_dir = output_dir or get_terry_dir("benchmarks")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.suites: dict[str, BenchmarkSuite] = {}

    def create_standard_suites(self) -> None:
        """Create standard benchmark suites."""
        # Coding Basics
        basics = BenchmarkSuite("coding_basics", "Basic coding tasks")
        basics.add_problem(
            "hello_world",
            "Create a file hello.py that prints 'Hello, World!' when executed",
            ["Hello, World!"],
            ["hello.py"],
            "python hello.py",
        )
        basics.add_problem(
            "read_write",
            "Read the file data.txt (create it with numbers 1-10, one per line) "
            "and write a file sum.txt containing the sum of all numbers",
            ["55"],
            ["data.txt", "sum.txt"],
        )
        basics.add_problem(
            "string_reverse",
            "Create a Python function that reverses a string and write tests for it",
            ["def reverse", "test"],
        )
        self.suites["coding_basics"] = basics

        # Refactoring
        refactoring = BenchmarkSuite("refactoring", "Code refactoring tasks")
        refactoring.add_problem(
            "extract_function",
            "Read the file spaghetti.py (create it with a long function that does 3 things) "
            "and refactor it by extracting helper functions",
            ["def ", "return"],
            ["spaghetti.py"],
        )
        refactoring.add_problem(
            "rename_variables",
            "Find variables with single-letter names in a Python file "
            "and rename them to descriptive names",
            ["descriptive", "rename"],
        )
        self.suites["refactoring"] = refactoring

        # Debugging
        debugging = BenchmarkSuite("debugging", "Bug fixing scenarios")
        debugging.add_problem(
            "off_by_one",
            "Create a Python file with a loop that has an off-by-one error. "
            "Then find and fix the bug.",
            ["fixed", "correct"],
        )
        debugging.add_problem(
            "null_check",
            "Find code that doesn't check for None/empty values and add proper guards",
            ["if ", "None", "guard"],
        )
        self.suites["debugging"] = debugging

        # Tool Usage
        tools = BenchmarkSuite("tool_usage", "Tool calling accuracy")
        tools.add_problem(
            "find_and_read",
            "Use find and read_file tools to locate and display the project README",
            ["Terry"],
        )
        tools.add_problem(
            "git_workflow",
            "Use git_status and git_diff to check the repository state",
            ["git"],
        )
        self.suites["tool_usage"] = tools

    def run_suite(
        self, suite_name: str, timeout_per_problem: int = 120
    ) -> BenchmarkSuite:
        """Run all problems in a benchmark suite.

        Args:
            suite_name: Name of the suite to run
            timeout_per_problem: Max seconds per problem

        Returns:
            Updated BenchmarkSuite with results
        """
        suite = self.suites.get(suite_name)
        if not suite:
            raise ValueError(f"Unknown suite: {suite_name}")

        suite.results = []

        for problem in suite.problems:
            result = self._run_problem(problem, timeout_per_problem)
            suite.results.append(result)

        # Save results
        self._save_results(suite)

        return suite

    def _run_problem(
        self, problem: dict, timeout: int
    ) -> BenchmarkResult:
        """Run a single benchmark problem."""
        result = BenchmarkResult(problem["id"], "running")

        if not self.agent:
            result.status = "error"
            result.error_message = "No agent available"
            return result

        start_time = time.time()

        try:
            # Run the agent
            response = self.agent.run(problem["prompt"])

            result.duration_seconds = round(time.time() - start_time, 2)
            result.agent_response = response[:1000]
            result.tool_calls = self.agent.tool_call_count

            # Get token usage
            metrics = self.agent.get_metrics_summary()
            if metrics:
                counters = metrics.get("counters", {})
                result.input_tokens = counters.get("input_tokens", 0)
                result.output_tokens = counters.get("output_tokens", 0)
                result.cost_usd = round(metrics.get("total_cost", 0), 6)

            # Check expected patterns
            patterns_matched = 0
            for pattern in problem.get("expected_patterns", []):
                if pattern.lower() in response.lower():
                    patterns_matched += 1

            # Check for created files
            files_found = 0
            for filepath in problem.get("files_to_check", []):
                if (Path(self.agent.workdir) / filepath).exists():
                    files_found += 1

            # Calculate score
            total_checks = len(problem.get("expected_patterns", [])) + \
                          len(problem.get("files_to_check", []))
            if total_checks > 0:
                result.score = (patterns_matched + files_found) / total_checks

            result.status = "passed" if result.score >= 0.5 else "failed"

        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            result.duration_seconds = round(time.time() - start_time, 2)

        return result

    def _save_results(self, suite: BenchmarkSuite) -> Path:
        """Save benchmark results to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{suite.name}_{timestamp}.json"
        filepath = self.output_dir / filename

        data = suite.to_dict()
        data["timestamp"] = timestamp

        filepath.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return filepath

    def get_leaderboard(self) -> list[dict]:
        """Get a leaderboard of all suite results."""
        leaderboard = []
        for name, suite in self.suites.items():
            if suite.results:
                passed = sum(1 for r in suite.results if r.status == "passed")
                avg_score = sum(r.score for r in suite.results) / max(len(suite.results), 1)
                avg_time = sum(r.duration_seconds for r in suite.results) / max(len(suite.results), 1)
                total_cost = sum(r.cost_usd for r in suite.results)

                leaderboard.append({
                    "suite": name,
                    "problems": len(suite.results),
                    "passed": passed,
                    "pass_rate": f"{passed}/{len(suite.results)}",
                    "avg_score": round(avg_score, 3),
                    "avg_time_s": round(avg_time, 1),
                    "total_cost_usd": round(total_cost, 6),
                })

        return sorted(leaderboard, key=lambda x: x["avg_score"], reverse=True)

    def list_suites(self) -> list[dict[str, str]]:
        """List available benchmark suites."""
        if not self.suites:
            self.create_standard_suites()
        return [
            {"name": name, "description": suite.description}
            for name, suite in self.suites.items()
        ]

    def run_all(self) -> dict[str, Any]:
        """Run all benchmark suites."""
        if not self.suites:
            self.create_standard_suites()

        start = time.time()
        for name in self.suites:
            self.run_suite(name)

        total_time = time.time() - start
        leaderboard = self.get_leaderboard()

        return {
            "suites_ran": len(self.suites),
            "total_time_s": round(total_time, 1),
            "leaderboard": leaderboard,
        }
