"""AutoHealer v2 — auto-fix test failures, lint errors, and type errors.

Extends the existing ErrorRecovery with:
- Test failure analysis + auto-fix suggestions (pytest output parsing)
- Lint auto-fix (ruff --fix runner)
- Type error analysis + annotation suggestions (mypy output parsing)

Usage:
    from terry.core.auto_healer_v2 import AutoHealerV2
    healer = AutoHealerV2(workdir)
    result = healer.heal_test_failures(pytest_output)
    result = healer.heal_lint_errors()
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HealResult:
    """Result of an auto-healing attempt."""

    category: str           # test, lint, type
    total_issues: int = 0
    fixed: int = 0
    suggestions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class AutoHealerV2:
    """Auto-fix common code quality issues: test failures, lint, type errors."""

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()

    # ── Test Failure Healing ──────────────────────────────────────

    def heal_test_failures(self, pytest_output: str) -> HealResult:
        """Parse pytest output and suggest/heal common failures."""
        result = HealResult(category="test")

        patterns = [
            (r"ModuleNotFoundError: No module named '(\w+)'",
             self._fix_missing_module, "missing_module"),
            (r"ImportError: cannot import name '(\w+)'",
             self._fix_bad_import, "bad_import"),
            (r"AssertionError: (.*)",
             self._suggest_assertion_fix, "assertion_error"),
            (r"AttributeError: .*has no attribute '(\w+)'",
             self._suggest_attribute_fix, "attribute_error"),
            (r"File \"([^\"]+)\", line (\d+)",
             self._locate_failure, "failure_location"),
        ]

        for pattern, handler, name in patterns:
            matches = re.findall(pattern, pytest_output)
            for match in matches:
                try:
                    suggestion = handler(match) if not isinstance(match, tuple) else handler(*match)
                    if suggestion:
                        result.suggestions.append(suggestion)
                except Exception:
                    pass

        result.total_issues = len(result.suggestions)
        result.fixed = 0  # Suggestions only, user reviews before applying
        return result

    def _fix_missing_module(self, module_name: str) -> str | None:
        """Suggest installing a missing Python module."""
        if not module_name.isidentifier():
            return None
        return (f"Missing module '{module_name}'. Try: "
                f"pip install {module_name}  "
                f"(or add to requirements.txt if it's a project dependency)")

    def _fix_bad_import(self, name: str) -> str:
        return (
            f"Import error for '{name}'. Check: "
            "1) correct module path, 2) circular import, 3) removed/renamed symbol"
        )

    def _suggest_assertion_fix(self, message: str) -> str:
        return f"Assertion failed: {message[:100]}. Review test logic — expected vs actual mismatch."

    def _suggest_attribute_fix(self, attr: str) -> str:
        return (
            f"AttributeError on '{attr}'. Check: "
            "1) typo in name, 2) None where object expected, 3) missing __init__"
        )

    def _locate_failure(self, filepath: str, line: str) -> str | None:
        full = self.workdir / filepath
        if not full.exists():
            return None
        try:
            lines = full.read_text().split("\n")
            line_num = int(line) - 1
            if 0 <= line_num < len(lines):
                return f"Failure at {filepath}:{line}: `{lines[line_num].strip()[:100]}`"
        except (OSError, ValueError):
            pass
        return None

    # ── Lint Error Healing ────────────────────────────────────────

    def heal_lint_errors(self, paths: list[str] | None = None) -> HealResult:
        """Run ruff --fix to auto-fix lint errors."""
        result = HealResult(category="lint")
        targets = paths or ["terry/", "tests/"]

        try:
            proc = subprocess.run(
                ["python3", "-m", "ruff", "check"] + targets + ["--fix"],
                cwd=self.workdir, capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                result.fixed = 0
                result.suggestions.append("No lint errors found — code is clean")
            else:
                # Count remaining errors
                remaining = len([line for line in proc.stdout.split("\n") if line.strip()])
                result.total_issues = remaining
                result.fixed = 0  # ruff --fix handles the auto-fixable ones
                if remaining > 0:
                    result.suggestions.append(
                        f"{remaining} lint errors remain after auto-fix. "
                        f"Run: ruff check --output-format=concise"
                    )
                else:
                    result.fixed = 1
                    result.suggestions.append("All auto-fixable lint errors resolved")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result.errors.append(str(e))

        return result

    # ── Type Error Healing ────────────────────────────────────────

    def heal_type_errors(self, mypy_output: str) -> HealResult:
        """Parse mypy output and suggest type annotation fixes."""
        result = HealResult(category="type")

        patterns: dict[str, str] = {
            r"Missing return statement": "Add return type annotation or return statement",
        }

        for pattern, message in patterns.items():
            if re.search(pattern, mypy_output):
                result.suggestions.append(message)

        result.total_issues = len(result.suggestions)
        return result

    # ── Full Heal ─────────────────────────────────────────────────

    def heal_all(self) -> dict[str, HealResult]:
        """Run all healers and return combined results."""
        results: dict[str, HealResult] = {}

        # Lint (runs independently)
        results["lint"] = self.heal_lint_errors()

        # Test (needs pytest output)
        try:
            proc = subprocess.run(
                ["python3", "-m", "pytest", "tests/", "-q", "--tb=short"],
                cwd=self.workdir, capture_output=True, text=True, timeout=120,
            )
            results["test"] = self.heal_test_failures(proc.stdout + proc.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            results["test"] = HealResult(category="test",
                                          errors=["pytest not available"])

        # Type (needs mypy)
        try:
            proc = subprocess.run(
                ["python3", "-m", "mypy", "terry/", "--ignore-missing-imports"],
                cwd=self.workdir, capture_output=True, text=True, timeout=120,
            )
            results["type"] = self.heal_type_errors(proc.stdout + proc.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            results["type"] = HealResult(category="type",
                                          errors=["mypy not installed"])

        return results
