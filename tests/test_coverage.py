"""Comprehensive coverage tests targeting critical uncovered paths."""

from __future__ import annotations

import tempfile
import json
from pathlib import Path

import pytest


# ── Core: store.py ─────────────────────────────────────────────────

class TestTerryStore:
    def test_kv_set_get(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            store.kv_set("test", "key1", "value1")
            assert store.kv_get("test", "key1") == "value1"
            assert store.kv_get("test", "missing", "default") == "default"
            store.kv_delete("test", "key1")
            assert store.kv_get("test", "key1") == ""

    def test_kv_list(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            store.kv_set("ns", "a", "1")
            store.kv_set("ns", "b", "2")
            data = store.kv_list("ns")
            assert data == {"a": "1", "b": "2"}

    def test_doc_save_get(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            store.doc_save("sessions", "s1", "hello", {"tag": "x"})
            doc = store.doc_get("s1")
            assert doc["content"] == "hello"
            assert json.loads(doc["metadata"]) == {"tag": "x"}
            store.doc_delete("s1")
            assert store.doc_get("s1") is None

    def test_doc_list(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            store.doc_save("coll", "d1", "a")
            store.doc_save("coll", "d2", "b")
            docs = store.doc_list("coll")
            assert len(docs) == 2

    def test_event_log(self):
        with tempfile.TemporaryDirectory() as d:
            from terry import __version__
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            store.event_log("agent_start", {"version": __version__})
            events = store.event_query("agent_start", limit=10)
            assert len(events) == 1

    def test_stats(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "test.db")
            stats = store.stats()
            assert "kv_entries" in stats


# ── Core: telemetry.py ────────────────────────────────────────────

class TestTelemetry:
    def test_span_lifecycle(self):
        from terry.core.telemetry import Span
        span = Span("test_op")
        span.set_attribute("key", "val")
        span.add_event("step1", {"result": "ok"})
        span.set_status("ok")
        span.finish()
        assert span.duration_ms >= 0
        assert span.attributes["key"] == "val"

    def test_metrics_registry(self):
        from terry.core.telemetry import MetricsRegistry
        m = MetricsRegistry()
        m.increment("calls", 3)
        m.increment("calls")
        m.record_histogram("latency", 10.5)
        m.record_histogram("latency", 20.0)
        m.set_gauge("active", 5)
        snap = m.snapshot()
        assert snap["counters"]["calls"] == 4
        assert snap["gauges"]["active"] == 5

    def test_trace_context_manager(self):
        from terry.core.telemetry import Telemetry
        tel = Telemetry()
        with tel.trace("test.trace", msg="hello") as span:
            span.set_attribute("extra", "data")
            tel.event("midpoint", step=1)
        snap = tel.snapshot()
        assert snap["service"] == "terry"

    def test_error_tracking(self):
        from terry.core.telemetry import Telemetry
        tel = Telemetry()
        with tel.trace("test.error"):
            tel.error("llm_call", ValueError("boom"))
        snap = tel.snapshot()
        assert "llm_call.errors" in snap["metrics"]["counters"]


# ── Core: eval_runner.py ──────────────────────────────────────────

class TestEvalRunner:
    def test_golden_dataset(self):
        from terry.core.eval_runner import GOLDEN_DATASET
        assert len(GOLDEN_DATASET) >= 8
        categories = {tc.category for tc in GOLDEN_DATASET}
        assert "basic" in categories
        assert "safety" in categories

    def test_run_all_no_agent(self):
        from terry.core.eval_runner import EvalRunner
        runner = EvalRunner(agent_factory=None)
        report = runner.run_all()
        assert "total" in report
        assert isinstance(report["results"], list)

    def test_regression_detection(self):
        from terry.core.eval_runner import EvalRunner
        runner = EvalRunner()
        baseline = {"results": [{"name": "t1", "score": 0.9}]}
        current = {"results": [{"name": "t1", "score": 0.5}]}
        result = runner.detect_regression(baseline, current)
        assert result["regression_detected"]


# ── Core: feedback.py ─────────────────────────────────────────────

class TestFeedbackMore:
    def test_load_history(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector(sample_rate=0.0)
        history = fc.load_history(limit=5)
        assert isinstance(history, list)

    def test_maybe_prompt_skipped(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector(sample_rate=0.0)
        result = fc.maybe_prompt("test", "response")
        assert result is None


# ── Core: ux.py ───────────────────────────────────────────────────

class TestUXMore:
    def test_first_run_wizard_complete(self):
        from terry.core.ux import FirstRunWizard
        welcome = FirstRunWizard.get_welcome()
        assert "Welcome" in welcome or "Try" in welcome

    def test_friendly_errors_module_not_found(self):
        from terry.core.ux import FriendlyErrors
        msg = FriendlyErrors.translate("ModuleNotFoundError: No module named 'xyz'", {"module": "xyz"})
        assert "pip install" in msg.lower()

    def test_friendly_errors_api_key(self):
        from terry.core.ux import FriendlyErrors
        msg = FriendlyErrors.translate("API key not configured")
        assert "ANTHROPIC_API_KEY" in msg

    def test_tips_random(self):
        from terry.core.ux import TipsEngine
        tip = TipsEngine.get_random_tip()
        assert tip and "💡" in tip

    def test_tips_context_fix(self):
        from terry.core.ux import TipsEngine
        tip = TipsEngine.get_tip_for_context(message="fix the bug")
        assert tip and "/undo" in tip

    def test_tips_context_refactor(self):
        from terry.core.ux import TipsEngine
        tip = TipsEngine.get_tip_for_context(message="refactor the module")
        assert tip and "/plan" in tip

    def test_formatter_success(self):
        from terry.core.ux import UXFormatter
        assert "✅" in UXFormatter.success("Done")

    def test_formatter_warning(self):
        from terry.core.ux import UXFormatter
        assert "⚠️" in UXFormatter.warning("Careful")


# ── Core: thinking.py ─────────────────────────────────────────────

class TestThinkingMore:
    def test_suggest_compression_zero_messages(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        threshold = et.suggest_compression_threshold([], "")
        assert 0 <= threshold <= 1.0

    def test_estimate_history_tokens(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        tokens = et.estimate_history_tokens([{"role": "user", "content": "hi"}])
        assert tokens >= 0

    def test_optimize_allocation(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        budgets = et.optimize_allocation([{"role": "user", "content": "test"}], "system")
        assert "output" in budgets


# ── Core: task_dag.py ─────────────────────────────────────────────

class TestTaskDAGMore:
    def test_mark_status(self):
        from terry.core.task_dag import TaskDAG, TaskNode
        dag = TaskDAG()
        tid = dag.add_task("Test")
        assert dag.mark_status(tid, "completed")
        assert dag.mark_status("nonexistent", "done") is False

    def test_get_blocked(self):
        from terry.core.task_dag import TaskDAG, TaskNode
        dag = TaskDAG()
        t1 = dag.add_task("Task 1")
        t2 = dag.add_task("Task 2", depends_on=[t1])
        blocked = dag.get_blocked_tasks()
        assert any(t.id == t2 for t in blocked)

    def test_list_by_status(self):
        from terry.core.task_dag import TaskDAG
        dag = TaskDAG()
        dag.add_task("T1")
        pending = dag.list_by_status("pending")
        assert len(pending) >= 1


# ── Core: commands.py ─────────────────────────────────────────────

class TestCommandRegistry:
    def test_register_and_dispatch(self):
        from terry.core.commands import Command, CommandRegistry
        cr = CommandRegistry()
        results = []
        def handler(cmd, args, agent):
            results.append(cmd)
            return True
        cr.register(Command("/test", handler, "Test command", "basic"))
        result = cr.dispatch("/test", None)
        assert result is True
        assert "/test" in results

    def test_suggest(self):
        from terry.core.commands import Command, CommandRegistry
        cr = CommandRegistry()
        def dummy(cmd, args, agent): return True
        cr.register(Command("/help", dummy, "Help", "basic"))
        cr.register(Command("/hello", dummy, "Hello", "basic"))
        suggestions = cr.suggest("/hel")
        assert "/help" in suggestions

    def test_get_categories(self):
        from terry.core.commands import Command, CommandRegistry
        cr = CommandRegistry()
        def dummy(cmd, args, agent): return True
        cr.register(Command("/test1", dummy, "T1", "basic"))
        cr.register(Command("/test2", dummy, "T2", "safety"))
        cats = cr.get_categories()
        assert "basic" in cats
        assert "safety" in cats


# ── Core: permissions.py ──────────────────────────────────────────

class TestPermissionsMore:
    def test_permission_level_cycle(self):
        from terry.core.permissions import PermissionLevel
        assert PermissionLevel.cycle(PermissionLevel.LOW) == PermissionLevel.MEDIUM
        assert PermissionLevel.cycle(PermissionLevel.CRITICAL) == PermissionLevel.LOW

    def test_permission_rule_expired(self):
        from terry.core.permissions import PermissionRule
        rule = PermissionRule("bash", "*", "ask", expires_at="2020-01-01T00:00:00")
        assert rule.is_expired()

    def test_permission_store_remove_rule(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.permissions import PermissionStore, PermissionRule
            store = PermissionStore(path=Path(d) / "perms.json")
            store.add_rule(PermissionRule("bash", "echo *", "allow"))
            assert store.remove_rule("bash", "echo *")
            assert not store.remove_rule("nonexistent", "nonexistent")

    def test_permission_store_clear_user(self):
        from terry.core.permissions import PermissionStore
        count = PermissionStore().clear_user_rules()
        assert count >= 0


# ── Core: session.py ──────────────────────────────────────────────

class TestSessionMore:
    def test_session_clear(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            s.new()
            s.add_message("user", "hello")
            s.clear()
            assert len(s.get_messages()) == 0

    def test_session_increment_tool_calls(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            s.new()
            s.increment_tool_calls(5)
            s.increment_tool_calls(3)
            assert s.metadata["tool_calls"] == 8

    def test_session_add_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            s.new()
            s.add_tokens(1000)
            assert s.metadata["tokens_used"] == 1000

    def test_session_delete(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            s.new("test_session")
            assert s.delete()

    def test_list_sessions_empty(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            sessions = Session.list_sessions(Path(d))
            assert isinstance(sessions, list)


# ── Tools: bash.py ────────────────────────────────────────────────

class TestBashTool:
    def test_execute_echo(self):
        from terry.tools.bash import BashTool
        tool = BashTool(workdir=Path.cwd())
        result = tool.execute(command="echo hello")
        assert "hello" in result

    def test_empty_command(self):
        from terry.tools.bash import BashTool
        result = BashTool().execute(command="")
        assert isinstance(result, str)


# ── Tools: grep tool ──────────────────────────────────────────────

class TestGrepTool:
    def test_grep_simple(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "test.py").write_text("def foo():\n    return 'bar'\n")
            from terry.tools.grep_tool import GrepTool
            tool = GrepTool(workdir=Path(d))
            result = tool.execute(pattern="def foo")
            assert "test.py" in result or "foo" in result


# ── Tools: find tool ──────────────────────────────────────────────

class TestFindTool:
    def test_find_py(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mod.py").write_text("")
            from terry.tools.find_tool import FindTool
            tool = FindTool(workdir=Path(d))
            result = tool.execute(pattern="*.py")
            assert "mod.py" in result


# ── Tools: glob tool ──────────────────────────────────────────────

class TestGlobTool:
    def test_glob_py(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "hello.py").write_text("")
            from terry.tools.glob_tool import GlobTool
            tool = GlobTool(workdir=Path(d))
            result = tool.execute(pattern="*.py")
            assert "hello.py" in result


# ── Tools: write_file ─────────────────────────────────────────────

class TestWriteFileTool:
    def test_write_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.write_file import WriteFileTool
            tool = WriteFileTool(workdir=Path(d))
            result = tool.execute(path="test.txt", content="hello")
            assert "Wrote" in result
            assert (Path(d) / "test.txt").read_text() == "hello"

    def test_write_escaped_path(self):
        from terry.tools.write_file import WriteFileTool
        result = WriteFileTool().execute(path="../../etc/passwd", content="x")
        assert "Error" in result or "escape" in result.lower()


# ── Tools: read_file ──────────────────────────────────────────────

class TestReadFileTool:
    def test_read_existing(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data.txt").write_text("line1\nline2\nline3\n")
            from terry.tools.read_file import ReadFileTool
            tool = ReadFileTool(workdir=Path(d))
            result = tool.execute(path="data.txt", limit=2)
            assert "line1" in result
            assert result.count("line") <= 3

    def test_read_missing(self):
        from terry.tools.read_file import ReadFileTool
        result = ReadFileTool().execute(path="no_such_file.txt")
        assert "Error" in result or "not found" in result.lower()


# ── Tools: ls ─────────────────────────────────────────────────────

class TestLsTool:
    def test_ls_directory(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "file1.py").write_text("")
            (Path(d) / "file2.md").write_text("")
            from terry.tools.ls_tool import LsTool
            tool = LsTool(workdir=Path(d))
            result = tool.execute(path=".")
            assert "file1.py" in result
            assert "file2.md" in result


# ── Tools: todo_write ─────────────────────────────────────────────

class TestTodoWriteTool:
    def test_write_todos(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.todo_write import TodoWriteTool
            tool = TodoWriteTool(workdir=Path(d))
            result = tool.execute(todos=[
                {"content": "Task A", "status": "pending"},
                {"content": "Task B", "status": "completed"},
            ])
            assert isinstance(result, str)

    def test_invalid_todo(self):
        from terry.tools.todo_write import TodoWriteTool
        result = TodoWriteTool().execute(todos=[{"invalid": "data"}])
        assert "Error" in result or "invalid" in result.lower()


# ── Tools: weather ────────────────────────────────────────────────

class TestWeatherTool:
    def test_no_api_key(self):
        os_unset = __import__('os').environ.pop
        old = __import__('os').environ.get('WEATHER_API_KEY')
        try:
            __import__('os').environ.pop('WEATHER_API_KEY', None)
            __import__('os').environ.pop('OPENWEATHERMAP_API_KEY', None)
            from terry.tools.weather import WeatherTool
            result = WeatherTool().execute(location="Beijing")
            assert "Error" in result or "API key" in result or "key" in result.lower()
        finally:
            if old:
                __import__('os').environ['WEATHER_API_KEY'] = old


# ── Tools: notebook ───────────────────────────────────────────────

class TestNotebookTool:
    def test_invalid_file(self):
        from terry.tools.notebook import NotebookEditTool
        result = NotebookEditTool().execute(path="not_a_notebook.txt", edit_mode="replace")
        assert "Error" in result or "ipynb" in result.lower()

    def test_invalid_mode(self):
        from terry.tools.notebook import NotebookEditTool
        result = NotebookEditTool().execute(path="test.ipynb", edit_mode="unknown_mode")
        assert "Error" in result


# ── Git tools ────────────────────────────────────────────────────

class TestGitTools:
    def test_git_status_no_repo(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.git.git_status import GitStatusTool
            result = GitStatusTool(workdir=Path(d)).execute()
            assert "Error" in result or "git" in result.lower()

    def test_git_diff_no_repo(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.git.git_diff import GitDiffTool
            result = GitDiffTool(workdir=Path(d)).execute()
            assert "Error" in result or "git" in result.lower()

    def test_git_commit_no_repo(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.git.git_commit import GitCommitTool
            result = GitCommitTool(workdir=Path(d)).execute(message="test")
            assert "Error" in result or "git" in result.lower()

    def test_git_log_no_repo(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.git.git_log import GitLogTool
            result = GitLogTool(workdir=Path(d)).execute()
            assert "Error" in result or "git" in result.lower()

    def test_git_checkout_no_branch(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.git.git_checkout import GitCheckoutTool
            result = GitCheckoutTool(workdir=Path(d)).execute()
            assert "Error" in result or "specify" in result.lower()


# ── Core: adapter ─────────────────────────────────────────────────

class TestAdapter:
    def test_get_provider(self):
        from terry.core.adapter import get_provider, PROVIDERS
        assert get_provider("anthropic") is not None
        assert get_provider("nonexistent") is None

    def test_list_providers(self):
        from terry.core.adapter import list_providers
        providers = list_providers()
        assert len(providers) >= 6

    def test_register_custom_provider(self):
        from terry.core.adapter import register_provider, ProviderAdapter
        register_provider(ProviderAdapter(
            name="TestProvider", base_url="https://test.api/v1",
            default_model="test-model", key_env="TEST_KEY"
        ))
        from terry.core.adapter import get_provider
        assert get_provider("testprovider") is not None


# ── Core: config ──────────────────────────────────────────────────

class TestConfigMore:
    def test_sandbox_mode_validation(self):
        from terry.core.config import TerryConfig
        cfg = TerryConfig()
        cfg.sandbox_mode = "invalid"
        issues = cfg.validate()
        assert any("sandbox_mode" in i for i in issues)

    def test_model_resolve(self):
        from terry.core.config import ModelConfig
        mc = ModelConfig(provider="anthropic")
        mc.resolve()
        assert mc.base_url is not None


# ── Core: logger ──────────────────────────────────────────────────

class TestLoggerMore:
    def test_logger_critical(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.logger import Logger
            logger = Logger(name="test", log_dir=Path(d), console=False, file=True)
            logger.critical("Critical issue")
            log_content = (Path(d) / "test.log").read_text()
            assert "Critical issue" in log_content

    def test_json_formatter(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.logger import Logger
            logger = Logger(name="test", log_dir=Path(d), console=False, file=True, json_format=False)
            logger.info("test_msg")
            assert (Path(d) / "test.log").exists()


# ── Core: metrics ─────────────────────────────────────────────────

class TestMetricsMore:
    def test_timer_stats_empty(self):
        from terry.core.metrics import Metrics
        m = Metrics()
        stats = m.get_timer_stats("nonexistent")
        assert stats["count"] == 0

    def test_cost_estimate_unknown_model(self):
        from terry.core.metrics import estimate_cost
        cost = estimate_cost("unknown-model-xyz", 1000, 500)
        assert cost >= 0

    def test_metrics_reset(self):
        from terry.core.metrics import Metrics
        m = Metrics()
        m.increment("test", 10)
        m.reset()
        assert m.get_counter("test") == 0


# ── Core: cache ───────────────────────────────────────────────────

class TestCacheMore:
    def test_cache_cleanup_expired(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.cache import Cache
            cache = Cache(cache_dir=Path(d), default_ttl=0)
            cache.set("key", "value", ttl=0)
            import time; time.sleep(0.1)
            removed = cache.cleanup_expired()
            assert removed >= 1
            assert cache.get("key") is None


# ── Core: skill ───────────────────────────────────────────────────

class TestSkillMore:
    def test_skill_manager_no_skills_dir(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.skill import SkillManager
            sm = SkillManager(skills_dirs=[Path(d)])
            assert len(sm.list_skills()) == 0

    def test_skill_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.skill import SkillManager
            sm = SkillManager(skills_dirs=[Path(d)])
            assert sm.get_skill("nonexistent") is None


# ── Core: knowledge_graph ─────────────────────────────────────────

class TestKnowledgeGraphMore:
    def test_remove_node(self):
        from terry.core.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_node("X")
        kg.add_node("Y")
        kg.add_edge("X", "Y", "calls")
        assert kg.remove_node("X")
        assert not kg.remove_node("nonexistent")

    def test_graph_stats(self):
        from terry.core.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_node("A", properties={"name": "test"})
        stats = kg.get_stats()
        assert stats["nodes"] >= 1


# ── Core: memory_sync ─────────────────────────────────────────────

class TestMemorySyncMore:
    def test_sync_cloud_error(self):
        from terry.core.memory_sync import MemorySync
        ms = MemorySync()
        result = ms.sync_from_cloud("http://localhost:19999")
        assert result["ok"] is False

    def test_compute_hash(self):
        from terry.core.memory_sync import MemorySync
        ms = MemorySync()
        h1 = ms.compute_hash("hello")
        h2 = ms.compute_hash("hello")
        assert h1 == h2
        assert ms.compute_hash("world") != h1
