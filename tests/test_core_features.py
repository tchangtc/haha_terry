"""Pytest-standard tests for Terry core production features."""

import tempfile
from pathlib import Path

import pytest

from terry.core.memory import Memory
from terry.core.session import Session
from terry.core.metrics import Metrics
from terry.core.cache import Cache, LLMCache, ToolCache
from terry.core.logger import Logger
from terry.core.config import TerryConfig
from terry.core.agent import Agent


class TestMemorySystem:
    """Memory system tests."""

    def test_add_and_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = Memory(memory_dir=Path(tmpdir))
            memory.add("test-pref", "User prefers concise responses", "preference", "User communication preference")
            memory.add("proj-ctx", "Working on Terry AI agent", "context", "Current project")
            assert len(memory.list_memories()) == 2

    def test_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = Memory(memory_dir=Path(tmpdir))
            memory.add("test-pref", "User prefers concise responses", "preference", "User preference")
            content = memory.get("test-pref")
            assert content is not None
            assert "concise" in content

    def test_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = Memory(memory_dir=Path(tmpdir))
            memory.add("test-pref", "concise responses", "preference", "User preference")
            memory.add("proj-ctx", "Terry AI agent", "context", "Project")
            results = memory.search("Terry")
            assert len(results) == 1

    def test_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = Memory(memory_dir=Path(tmpdir))
            memory.add("test-pref", "concise responses", "preference", "User pref")
            memory.update("test-pref", "detailed responses")
            content = memory.get("test-pref")
            assert "detailed" in content

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = Memory(memory_dir=Path(tmpdir))
            memory.add("test-pref", "concise", "preference", "desc")
            memory.add("proj-ctx", "project", "context", "desc")
            memory.delete("proj-ctx")
            assert len(memory.list_memories()) == 1


class TestSessionSystem:
    """Session management tests."""

    def test_create_and_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Session(session_dir=Path(tmpdir))
            sid = session.new()
            assert sid is not None
            session.add_message("user", "Hello")
            session.add_message("assistant", "Hi!")
            assert len(session.get_messages()) == 2

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Session(session_dir=Path(tmpdir))
            sid = session.new()
            session.add_message("user", "Hello")
            session.save()

            new_session = Session(session_dir=Path(tmpdir))
            assert new_session.load(sid)
            assert len(new_session.get_messages()) == 1

    def test_list_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = Session(session_dir=Path(tmpdir))
            session.new()
            sessions = Session.list_sessions(Path(tmpdir))
            assert len(sessions) == 1


class TestMetricsSystem:
    """Metrics collection tests."""

    def test_counters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = Metrics(metrics_dir=Path(tmpdir))
            metrics.increment("tool_calls", 5)
            metrics.increment("tool_calls", 3)
            assert metrics.get_counter("tool_calls") == 8

    def test_timers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = Metrics(metrics_dir=Path(tmpdir))
            start = metrics.timer_start()
            duration = metrics.timer_stop("test_op", start)
            stats = metrics.get_timer_stats("test_op")
            assert stats["count"] == 1
            assert stats["total"] >= 0

    def test_cost_tracking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = Metrics(metrics_dir=Path(tmpdir))
            metrics.add_cost("anthropic", 0.05)
            metrics.add_cost("openai", 0.03)
            assert abs(metrics.get_total_cost() - 0.08) < 0.001

    def test_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = Metrics(metrics_dir=Path(tmpdir))
            summary = metrics.get_summary()
            assert "counters" in summary
            assert "costs" in summary

    def test_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics = Metrics(metrics_dir=Path(tmpdir))
            path = metrics.save("test_metrics.json")
            assert path.exists()


class TestCacheSystem:
    """Cache system tests."""

    def test_basic_get_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.set("key", "value")
            assert cache.get("key") == "value"

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.set("key", "value")
            cache.delete("key")
            assert cache.get("key") is None

    def test_llm_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            llm_cache = LLMCache(cache)
            messages = [{"role": "user", "content": "Test"}]
            response = {"content": "Response", "stop_reason": "end_turn"}
            llm_cache.set_response(messages, response, model="test-model")
            cached = llm_cache.get_response(messages, model="test-model")
            assert cached == response

    def test_tool_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            tool_cache = ToolCache(cache)
            tool_cache.set_result("bash", {"command": "ls"}, "output")
            assert tool_cache.get_result("bash", {"command": "ls"}) == "output"

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(cache_dir=Path(tmpdir))
            cache.set("key", "value")
            stats = cache.get_stats()
            assert "memory_entries" in stats


class TestLoggerSystem:
    """Logger tests."""

    def test_log_levels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger(name="test", log_dir=Path(tmpdir), console=False, file=True)
            logger.debug("Debug")
            logger.info("Info")
            logger.warning("Warning")
            logger.error("Error")
            log_file = Path(tmpdir) / "test.log"
            error_file = Path(tmpdir) / "test.error.log"
            assert log_file.exists()
            assert error_file.exists()

    def test_error_log_filtering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = Logger(name="test", log_dir=Path(tmpdir), console=False, file=True)
            logger.info("Info message")
            logger.error("Error message")
            error_content = (Path(tmpdir) / "test.error.log").read_text()
            assert "Error message" in error_content
            assert "Info message" not in error_content


class TestConfigSystem:
    """Configuration tests."""

    def test_defaults(self):
        config = TerryConfig()
        assert config.max_tool_calls == 50
        assert config.compression_threshold == 0.85
        assert config.sandbox_mode == "ask"

    def test_validate(self):
        config = TerryConfig()
        issues = config.validate()
        assert len(issues) == 0

    def test_validate_temperature(self):
        config = TerryConfig()
        config.model.temperature = 3.0
        issues = config.validate()
        assert any("temperature" in i for i in issues)

    def test_to_dict_excludes_api_key(self):
        config = TerryConfig()
        config.model.api_key = "sk-secret"
        d = config._to_dict()
        assert "api_key" not in d["model"]

    def test_register_default_providers(self):
        from terry.core.config import PROVIDER_REGISTRY
        assert "anthropic" in PROVIDER_REGISTRY
        assert "openai" in PROVIDER_REGISTRY


class TestAgentIntegration:
    """Agent integration tests."""

    def test_init(self):
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_metrics=True, enable_cache=True,
                      enable_subagents=False, enable_skills=True)
        status = agent.get_status()
        assert "workdir" in status
        assert "tools_available" in status
        assert "session_id" in status

    def test_build_system_prompt(self):
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_metrics=False, enable_cache=False,
                      enable_subagents=False, enable_skills=False,
                      enable_session=False, enable_memory=False)
        prompt = agent.build_system_prompt()
        assert "Terry" in prompt
        assert "coding agent" in prompt.lower()

    def test_clear_cache(self):
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_cache=True, enable_subagents=False)
        count = agent.clear_cache()
        assert count >= 0

    def test_reset(self):
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False)
        agent.reset()
        assert len(agent.messages) == 0
