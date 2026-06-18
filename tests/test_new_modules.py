"""Tests for v0.3.0 new modules — CLI, Harness, Feedback, Server, DynamicWorkflow, AutonomousAgent, MemorySync."""

import tempfile
from pathlib import Path

import pytest


class TestHarness:
    def test_all_patterns(self):
        from terry.core.harness import HarnessPattern
        patterns = list(HarnessPattern)
        assert len(patterns) == 8

    def test_engine_no_agent(self):
        from terry.core.harness import HarnessEngine
        engine = HarnessEngine(agent_factory=None)
        result = engine.execute("sequential", prompts=["task A", "task B"])
        assert "_metadata" in result

    def test_engine_checkpoint(self):
        from terry.core.harness import HarnessEngine
        engine = HarnessEngine()
        engine.create_task("test task", "do something")
        cp = engine.save_checkpoint()
        assert cp.exists()

    def test_harness_tool_registered(self):
        from terry.tools import discover_tools, tool_registry
        discover_tools()
        assert tool_registry.get("harness") is not None


class TestFeedback:
    def test_collector_init(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector(sample_rate=0.0)
        assert fc.sample_rate == 0.0

    def test_should_not_prompt_zero_rate(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector(sample_rate=0.0)
        assert not fc.should_prompt()

    def test_record_direct(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector()
        entry = fc.record_direct("good", user_message="test")
        assert entry.rating == "good"

    def test_get_stats(self):
        from terry.core.feedback import FeedbackCollector
        fc = FeedbackCollector()
        fc.record_direct("good")
        fc.record_direct("bad")
        stats = fc.get_stats()
        assert stats["good"] == 1
        assert stats["bad"] == 1


class TestDynamicWorkflow:
    def test_create_workflow(self):
        from terry.core.dynamic_workflow import DynamicWorkflow, WorkflowPattern
        wf = DynamicWorkflow("test", "goal")
        wf.add_stage("s1", "do something")
        assert len(wf.stages) == 1

    def test_engine_plan(self):
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern
        engine = DynamicWorkflowEngine()
        wf = engine.plan_workflow("fix bug", WorkflowPattern.FAN_OUT_MERGE)
        assert len(wf.stages) >= 1

    def test_checkpoint_list(self):
        from terry.core.dynamic_workflow import DynamicWorkflowEngine
        cps = DynamicWorkflowEngine().list_checkpoints()
        assert isinstance(cps, list)

    def test_resume_nonexistent(self):
        from terry.core.dynamic_workflow import DynamicWorkflowEngine
        assert DynamicWorkflowEngine().resume("nonexistent") is None


class TestAutonomousAgent:
    def test_submit_task(self):
        from terry.core.autonomous_agent import AutonomousAgent
        aa = AutonomousAgent(lambda: None)
        tid = aa.submit_task("fix bug")
        assert tid.startswith("auto_")

    def test_get_status(self):
        from terry.core.autonomous_agent import AutonomousAgent
        aa = AutonomousAgent(lambda: None)
        status = aa.get_status()
        assert "queued" in status

    def test_load_history(self):
        from terry.core.autonomous_agent import AutonomousAgent
        history = AutonomousAgent(lambda: None).load_task_history()
        assert isinstance(history, list)


class TestMemorySync:
    def test_export_import(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.memory_sync import MemorySync
            ms = MemorySync(memory_dir=Path(d))
            p = ms.export_memories()
            assert p.exists()
            count = ms.import_memories(p)
            assert count >= 0

    def test_get_changed_since(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.memory_sync import MemorySync
            ms = MemorySync(memory_dir=Path(d))
            changed = ms.get_changed_since("2020-01-01T00:00:00")
            assert isinstance(changed, list)


class TestServer:
    def test_init(self):
        from terry.server import TerryServer
        srv = TerryServer()
        assert srv.host == "127.0.0.1"
        assert srv.port == 8670

    def test_create_app(self):
        from terry.server import TerryServer
        srv = TerryServer()
        app = srv.create_app()
        assert callable(app)

    def test_status_stopped(self):
        from terry.server import TerryServer
        srv = TerryServer()
        status = srv.get_status()
        assert status == {"status": "stopped"}

    def test_chat_no_agent(self):
        from terry.server import TerryServer
        srv = TerryServer()
        result = srv.chat("hello")
        assert "error" in result


class TestCLIIntegration:
    def test_commands_registered(self):
        from terry.cli import app
        commands = {c.name for c in app.registered_commands}
        essential = {"run", "init", "webui", "desktop", "swe-bench"}
        assert essential <= commands

    def test_version(self):
        import re
        from terry import __version__
        # Semantic semver check: allows pre-release (-alpha.1, -rc1) and build (+sha123) suffixes.
        # Follows CHANGELOG.md versioning policy: Major.Minor.Patch per semver.org.
        semver_re = re.compile(r'^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$')
        assert semver_re.match(__version__), (
            f"Version '{__version__}' is not valid semver. "
            f"Expected format: X.Y.Z (e.g., 1.0.0, 1.0.1rc1, 1.0.0-alpha.1+build). "
            f"See CHANGELOG.md versioning policy."
        )


class TestHarnessToolRegistration:
    def test_tool_count(self):
        from terry.tools import discover_tools, tool_registry
        discover_tools()
        tools = tool_registry.list_tools()
        assert len(tools) >= 25


class TestCLIHelp:
    """CLI command structure tests."""

    def test_core_commands_registered(self):
        from terry.cli import app
        cmds = {c.name for c in app.registered_commands}
        for name in ("run", "webui", "desktop", "swe-bench", "init"):
            assert name in cmds, f"Missing command: {name}"

    def test_app_name(self):
        from terry.cli import app
        assert app.info.name == "terry"


class TestServerEndpoints:
    """Server API endpoint tests."""

    def test_health_endpoint(self):
        from terry.server import TerryServer
        srv = TerryServer()
        app_fn = srv.create_app()
        responses = []

        def start_response(status, headers):
            responses.append(status)

        environ = {"PATH_INFO": "/api/health", "REQUEST_METHOD": "GET"}
        result = app_fn(environ, start_response)
        assert len(result) > 0

    def test_status_endpoint(self):
        from terry.server import TerryServer
        srv = TerryServer()
        app_fn = srv.create_app()
        responses = []

        def start_response(status, headers):
            responses.append(status)

        environ = {"PATH_INFO": "/status", "REQUEST_METHOD": "GET"}
        result = app_fn(environ, start_response)
        assert len(result) > 0
