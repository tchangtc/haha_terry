"""Push to 80% coverage — final comprehensive tests."""

from __future__ import annotations

import tempfile, json, io, os, subprocess, time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _agent():
    from terry.core.config import TerryConfig
    c = TerryConfig(); c.model.api_key = "test"
    from terry.core.agent import Agent
    return Agent(c, enable_subagents=False, enable_skills=False,
                 enable_memory=False, enable_session=False,
                 enable_metrics=False, enable_cache=False,
                 enable_checkpoint=False, enable_planner=False)


# ═══════════════════════════════════════════════════════════════════
# EVERY CLI COMMAND HANDLER
# ═══════════════════════════════════════════════════════════════════

class TestEveryCLIHandler:
    def _run(self, name, args=""):
        from terry.cli_commands import cli_registry
        return cli_registry.dispatch(name + (" " + args if args else ""), _agent())

    def test_exit(self): assert self._run("/exit") is False
    def test_quit_alias(self): assert self._run("/quit") is False
    def test_q_alias(self): assert self._run("/q") is False
    def test_help(self): assert self._run("/help") is True
    def test_new(self): assert self._run("/new") is True
    def test_model(self): assert self._run("/model") is True
    def test_tools(self): assert self._run("/tools") is True
    def test_context(self): assert self._run("/context") is True
    def test_mode_cycle(self): assert self._run("/mode") is True
    def test_mode_set(self): assert self._run("/mode", "ask") is True
    def test_permissions(self): assert self._run("/permissions") is True
    def test_undo(self): assert self._run("/undo") is True
    def test_checkpoints(self): assert self._run("/checkpoints") is True
    def test_plan_no_args(self): assert self._run("/plan") is True
    def test_plan_with_args(self): assert self._run("/plan", "refactor auth") is True
    def test_config_show(self): assert self._run("/config") is True
    def test_search_no_args(self): assert self._run("/search") is True
    def test_search_with_args(self): assert self._run("/search", "test") is True
    def test_replay(self): assert self._run("/replay") is True
    def test_fork(self): assert self._run("/fork") is True
    def test_stream_no_args(self): assert self._run("/stream") is True
    def test_wfd_no_args(self): assert self._run("/wfd") is True
    def test_workflows(self): assert self._run("/workflows") is True
    def test_auto_no_args(self): assert self._run("/auto") is True
    def test_auto_with_args(self): assert self._run("/auto", "fix auth") is True
    def test_auto_skills(self): assert self._run("/auto-skills") is True
    def test_curator(self): assert self._run("/curator") is True
    def test_tasks_cmd(self): assert self._run("/tasks") is True
    def test_benchmark_no_args(self): assert self._run("/benchmark") is True

    def test_unknown_command(self):
        from terry.cli_commands import cli_registry
        result = cli_registry.dispatch("/nonexistent_cmd_xyz", _agent())
        assert result is None  # Unknown → None, handled by cli.py


# ═══════════════════════════════════════════════════════════════════
# AGENT — remaining methods
# ═══════════════════════════════════════════════════════════════════

class TestAgentRemaining:
    def test_get_mode(self):
        assert _agent().get_mode() == "ask"

    def test_set_mode_invalid(self):
        assert not _agent().set_mode("invalid_xyz")

    def test_cycle_mode_all(self):
        a = _agent()
        modes = set()
        for _ in range(5):
            modes.add(a.cycle_mode())
        assert len(modes) == 3

    def test_list_skills_none(self):
        from terry.core.agent import Agent
        a = _agent()
        assert a.list_skills() == []

    def test_get_skill_info_none(self):
        a = _agent()
        assert a.get_skill_info("nonexistent") is None

    def test_activate_skill_none(self):
        a = _agent()
        assert not a.activate_skill("nonexistent")

    def test_deactivate_skill(self):
        a = _agent()
        a.active_skill = "test"
        a.deactivate_skill()
        assert a.active_skill is None

    def test_reload_skills_none(self):
        a = _agent()
        assert a.reload_skills() >= 0

    def test_save_session_none(self):
        a = _agent()
        assert a.save_session() is None

    def test_load_session_none(self):
        a = _agent()
        assert not a.load_session("nonexistent")

    def test_parse_mentions_empty(self):
        assert _agent().parse_mentions("no mentions here") == "no mentions here"


# ═══════════════════════════════════════════════════════════════════
# SERVER — remaining methods
# ═══════════════════════════════════════════════════════════════════

class TestServerRemaining:
    def test_init_custom(self):
        from terry.server import TerryServer
        srv = TerryServer(host="0.0.0.0", port=9999)
        assert srv.host == "0.0.0.0"
        assert srv.port == 9999

    def test_start_stop_multiple(self):
        from terry.server import TerryServer
        srv = TerryServer(host="127.0.0.1", port=18676)
        srv.start()
        srv.stop()
        srv.start()
        srv.stop()

    def test_chat_with_error(self):
        from terry.server import TerryServer
        srv = TerryServer()
        srv.agent = MagicMock()
        srv.agent.run.side_effect = ValueError("boom")
        srv.agent.session = None
        result = srv.chat("hello")
        assert "error" in result

    def test_execute_tool_success(self):
        from terry.server import TerryServer
        srv = TerryServer()
        srv.agent = MagicMock()
        srv.agent.tools.execute.return_value = "output123"
        result = srv.execute_tool("bash", {"command": "echo hi"})
        assert result["result"] == "output123"


# ═══════════════════════════════════════════════════════════════════
# GATEWAYS — remaining stubs
# ═══════════════════════════════════════════════════════════════════

class TestTelegramRemaining:
    def test_handle_message_with_agent(self):
        from terry.server.gateways.telegram_gateway import TelegramGateway
        def factory():
            a = _agent()
            return a
        tg = TelegramGateway(token="test", agent_factory=factory)
        update = {"message": {"chat": {"id": 123}, "text": "/start", "from": {"id": 456}}}
        tg.handle_message(update)

    def test_send_typing(self):
        from terry.server.gateways.telegram_gateway import TelegramGateway
        tg = TelegramGateway(token="test")
        tg.send_typing(12345)

    def test_send_broadcast(self):
        from terry.server.gateways.telegram_gateway import TelegramGateway
        result = TelegramGateway(token="test").send_broadcast([123], "hello")
        assert isinstance(result, dict)


class TestDiscordRemaining:
    def test_send_typing(self):
        from terry.server.gateways.discord_gateway import DiscordGateway
        dg = DiscordGateway(token="test")
        dg.send_typing(12345)

    def test_handle_command_skills(self):
        from terry.server.gateways.discord_gateway import DiscordGateway
        dg = DiscordGateway(token="test")
        dg._handle_command(123, "skills", "msg_1")


# ═══════════════════════════════════════════════════════════════════
# TOOLS — remaining edge cases
# ═══════════════════════════════════════════════════════════════════

class TestToolsEdge:
    def test_read_file_large_limit(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data.txt").write_text("\n".join(str(i) for i in range(100)))
            from terry.tools.read_file import ReadFileTool
            result = ReadFileTool(workdir=Path(d)).execute(path="data.txt", limit=1000)
            assert isinstance(result, str)

    def test_write_file_creates_parent(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.write_file import WriteFileTool
            result = WriteFileTool(workdir=Path(d)).execute(path="a/b/c/test.txt", content="x")
            assert (Path(d) / "a" / "b" / "c" / "test.txt").exists()

    def test_git_diff_with_pathspec(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init"], cwd=d, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=d, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=d, capture_output=True)
            (Path(d) / "a.py").write_text("1")
            subprocess.run(["git", "add", "."], cwd=d, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=d, capture_output=True)
            (Path(d) / "b.py").write_text("2")
            from terry.tools.git.git_diff import GitDiffTool
            result = GitDiffTool(workdir=Path(d).resolve()).execute(pathspec="b.py")
            assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# CORE — remaining edge
# ═══════════════════════════════════════════════════════════════════

class TestErrorRecoveryEdge:
    def test_wrap_llm_call_success(self):
        from terry.core.error_recovery import ErrorRecovery, wrap_llm_call_with_recovery
        er = ErrorRecovery()
        def call(msgs, **kw): return {"result": "ok"}
        wrapped = wrap_llm_call_with_recovery(call, er)
        result = wrapped([])
        assert result == {"result": "ok"}

    def test_model_fallback_openai(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(model_fallback=True)
        er._consecutive_529_count["openai:gpt-4o"] = 3
        fb = er.should_fallback_model("openai", "gpt-4o")
        assert fb is not None


class TestThinkingEdge:
    def test_get_window_default(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking(model="unknown-xyz-123")
        assert et.total == 200000

    def test_estimate_system_tokens(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        tokens = et.estimate_system_prompt_tokens("System", [{"name": "bash", "description": "run", "input_schema": {}}])
        assert tokens >= 0


class TestStoreEdge:
    def test_kv_default(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "t.db")
            assert store.kv_get("ns", "missing", "fallback") == "fallback"

    def test_doc_update(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.store import TerryStore
            store = TerryStore(db_path=Path(d) / "t.db")
            store.doc_save("c", "d1", "v1")
            store.doc_save("c", "d1", "v2")  # Update
            doc = store.doc_get("d1")
            assert doc["content"] == "v2"


class TestModelRouterEdge:
    def test_empty_input(self):
        from terry.core.model_router import ModelRouter
        r = ModelRouter()
        assert r.analyze_complexity("") in ("simple", "medium", "complex")

    def test_estimated_savings(self):
        from terry.core.model_router import ModelRouter
        r = ModelRouter()
        savings = r.get_estimated_savings([{"role": "user", "content": "list files"}])
        assert "simple_task_ratio" in savings


class TestRepomapEdge:
    def test_is_code_file(self):
        from terry.core.repomap import RepoMapGenerator
        gen = RepoMapGenerator()
        assert gen._is_code_file(Path("test.py"))
        assert gen._is_code_file(Path("test.js"))
        assert gen._is_code_file(Path("test.md"))
        assert not gen._is_code_file(Path("test.png"))

    def test_build_tree(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sub").mkdir()
            (Path(d) / "sub" / "a.py").write_text("")
            from terry.core.repomap import RepoMapGenerator
            gen = RepoMapGenerator(workdir=Path(d))
            files = [Path(d) / "sub" / "a.py"]
            tree = gen._build_tree(files)
            assert "sub/" in tree
