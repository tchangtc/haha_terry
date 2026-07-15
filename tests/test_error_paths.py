"""Error-path tests using ``pytest.raises``.

Targets functions that *raise* on bad input — the calculator's safe AST
evaluator (``_safe_eval`` raises ``ValueError``; the public ``execute()``
catches it, so the evaluator is tested directly), the reminder time parser,
the search-provider registry's guard rails, and the benchmark suite lookup.
Each test pins a specific raise path and its message.
"""

from __future__ import annotations

import ast
from datetime import datetime

import pytest

from terry.core.benchmark import BenchmarkRunner
from terry.core.search_providers import SearchProviderRegistry
from terry.tools.calculator import CalculatorTool
from terry.tools.reminder import ReminderTool


# ── calculator: _safe_eval raise paths ──────────────────────────────


@pytest.fixture
def calc() -> CalculatorTool:
    return CalculatorTool()


def _node(expr: str) -> ast.AST:
    return ast.parse(expr, mode="eval")


class TestCalculatorSafeEvalRaises:
    def test_unknown_name(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unknown name: foo"):
            calc._safe_eval(_node("foo"))

    def test_unknown_function(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unknown function: bogus"):
            calc._safe_eval(_node("bogus(1)"))

    def test_too_many_arguments(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Too many arguments for function: max"):
            calc._safe_eval(_node("max(1,2,3,4,5,6)"))

    def test_result_exceeds_max_value(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Result exceeds maximum allowed value"):
            calc._safe_eval(_node("10**200"))

    def test_unsupported_expression_type(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            calc._safe_eval(_node("[1, 2]"))

    def test_unsupported_constant_type_string(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unsupported constant type: str"):
            calc._safe_eval(_node("'hello'"))

    def test_unsupported_unary_operator(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unsupported unary operator"):
            calc._safe_eval(_node("not 1"))

    def test_unsupported_binary_operator(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Unsupported binary operator"):
            calc._safe_eval(_node("1 @ 2"))

    def test_chained_comparison_rejected(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Only simple comparisons are supported"):
            calc._safe_eval(_node("1 < 2 < 3"))

    def test_attribute_call_rejected(self, calc: CalculatorTool):
        with pytest.raises(ValueError, match="Only simple function calls are supported"):
            calc._safe_eval(_node("math.sqrt(4)"))

    def test_recursion_depth_exceeded(self, calc: CalculatorTool):
        # 120 additions → left-spine depth well over MAX_RECURSION (100).
        with pytest.raises(ValueError, match="max recursion depth"):
            calc._safe_eval(_node("1+" * 120 + "1"))

    def test_execute_surfaces_value_error_as_message(self, calc: CalculatorTool):
        # The public execute() catches ValueError and returns an Error string.
        assert "Unknown name: foo" in calc.execute(expression="foo")


# ── reminder: time parsing ──────────────────────────────────────────


class TestReminderParseTime:
    def _tool(self, monkeypatch, tmp_path) -> ReminderTool:
        # reminder binds get_terry_dir at module import (from ..core.platform_utils
        # import get_terry_dir), so patch ITS reference, not the platform_utils attr.
        monkeypatch.setattr("terry.tools.reminder.get_terry_dir", lambda *a, **k: tmp_path)
        return ReminderTool()

    def test_relative_hours_parse(self, monkeypatch, tmp_path):
        tool = self._tool(monkeypatch, tmp_path)
        result = tool._parse_time("+2h")
        assert isinstance(result, datetime)
        assert result > datetime.now()

    def test_unparseable_time_raises(self, monkeypatch, tmp_path):
        tool = self._tool(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Unable to parse time: not-a-real-time"):
            tool._parse_time("not-a-real-time")

    def test_relative_with_unknown_unit_falls_through_to_error(self, monkeypatch, tmp_path):
        tool = self._tool(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Unable to parse time"):
            tool._parse_time("+5x")


# ── search providers: guard rails ───────────────────────────────────


class TestSearchProviderRegistryRaises:
    def _registry(self, monkeypatch, tmp_path) -> SearchProviderRegistry:
        monkeypatch.setattr("terry.core.platform_utils.get_terry_dir", lambda *a, **k: tmp_path)
        return SearchProviderRegistry()

    def test_cannot_remove_builtin(self, monkeypatch, tmp_path):
        reg = self._registry(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Cannot remove built-in provider: duckduckgo"):
            reg.remove("duckduckgo")

    def test_set_default_unknown_raises(self, monkeypatch, tmp_path):
        reg = self._registry(monkeypatch, tmp_path)
        with pytest.raises(ValueError, match="Unknown provider: no-such-provider"):
            reg.set_default("no-such-provider")

    def test_remove_then_set_default_unknown_still_raises(self, monkeypatch, tmp_path):
        reg = self._registry(monkeypatch, tmp_path)
        reg.register("custom", "https://example/?q={query}")
        reg.remove("custom")  # non-built-in removal succeeds
        assert reg.get("custom") is None
        with pytest.raises(ValueError, match="Unknown provider: custom"):
            reg.set_default("custom")


# ── benchmark: suite lookup ─────────────────────────────────────────


class TestBenchmarkRunSuiteRaises:
    def test_unknown_suite_raises(self, tmp_path):
        runner = BenchmarkRunner(agent=None, output_dir=tmp_path)
        # suites starts empty (create_standard_suites not called), so any name misses.
        with pytest.raises(ValueError, match="Unknown suite: nope"):
            runner.run_suite("nope")

    def test_known_suite_does_not_raise_on_lookup(self, tmp_path):
        runner = BenchmarkRunner(agent=None, output_dir=tmp_path)
        runner.create_standard_suites()
        assert "coding_basics" in runner.suites
        # run_suite would need an agent to actually execute; we only assert the
        # suite is now present so the Unknown-suite path no longer triggers.
        # (We do not call run_suite here to avoid spawning a real agent.)
        assert runner.suites["coding_basics"].name == "coding_basics"
