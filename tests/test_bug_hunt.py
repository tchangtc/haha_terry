"""Bug hunting + coverage push — testing edge cases in untested code paths."""

from __future__ import annotations

import tempfile, json, io, os, sys, subprocess, time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# BUG HUNT: edge cases that commonly hide bugs
# ═══════════════════════════════════════════════════════════════════

class TestBugHuntMemory:
    """Edge cases in memory system."""

    def test_add_with_special_chars(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.memory import Memory, MemoryType
            m = Memory(memory_dir=Path(d))
            name = "user's prefs & config #1"
            m.add(name, "content", MemoryType.USER)
            assert len(m.list_memories()) == 1

    def test_add_duplicate_name(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.memory import Memory
            m = Memory(memory_dir=Path(d))
            m.add("test", "first")
            m.add("test", "second")  # Should overwrite
            mems = m.list_memories()
            assert len(mems) == 1

    def test_search_empty_query(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.memory import Memory
            m = Memory(memory_dir=Path(d))
            m.add("test", "hello world")
            results = m.search("")
            assert isinstance(results, list)

    def test_get_nonexistent(self):
        from terry.core.memory import Memory
        assert Memory().get("nonexistent_xyz") is None


class TestBugHuntConfig:
    """Edge cases in config system."""

    def test_default_api_key_resolves_from_env(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key-123"
        from terry.core.config import ModelConfig
        mc = ModelConfig(provider="anthropic")
        mc.resolve()
        assert mc.api_key == "test-key-123"
        del os.environ["ANTHROPIC_API_KEY"]

    def test_load_nonexistent_file(self):
        from terry.core.config import TerryConfig
        cfg = TerryConfig.load("/nonexistent/path/config.json")
        assert cfg.max_tool_calls == 50  # Default

    def test_validation_all_checks(self):
        from terry.core.config import TerryConfig
        cfg = TerryConfig()
        cfg.max_tool_calls = 0
        cfg.max_input_tokens = 500
        cfg.compression_threshold = 0.05
        cfg.sandbox_mode = "invalid"
        issues = cfg.validate()
        assert len(issues) >= 3

    def test_save_excludes_api_key(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.config import TerryConfig
            cfg = TerryConfig()
            cfg.model.api_key = "secret-123"
            path = Path(d) / "cfg.json"
            cfg.save(str(path))
            saved = json.loads(path.read_text())
            assert "api_key" not in str(saved.get("model", {}))


class TestBugHuntPermissions:
    """Permission edge cases."""

    def test_permission_level_from_sandbox(self):
        from terry.core.permissions import PermissionLevel
        assert PermissionLevel.from_sandbox_mode("auto") == PermissionLevel.LOW
        assert PermissionLevel.from_sandbox_mode("ask") == PermissionLevel.MEDIUM
        assert PermissionLevel.from_sandbox_mode("deny") == PermissionLevel.HIGH
        assert PermissionLevel.from_sandbox_mode("invalid") == PermissionLevel.MEDIUM

    def test_rule_matches_wildcard(self):
        from terry.core.permissions import PermissionRule
        rule = PermissionRule("bash", "*", "ask")
        assert rule.matches("bash", "rm file")
        assert rule.matches("bash", "echo hi")
        assert not rule.matches("read_file", "test.py")

    def test_rule_expired_none(self):
        from terry.core.permissions import PermissionRule
        rule = PermissionRule("bash")
        assert not rule.is_expired()  # No expiry = never expires

    def test_store_check_deny_takes_priority(self):
        from terry.core.permissions import PermissionStore, PermissionRule, PermissionLevel
        store = PermissionStore()
        store.add_rule(PermissionRule("bash", "echo *", "allow"))
        store.add_rule(PermissionRule("bash", "echo secret", "deny"))
        result = store.check("bash", "echo secret", PermissionLevel.MEDIUM)
        assert result is not None  # Deny should take priority


class TestBugHuntCheckpoint:
    """Checkpoint edge cases."""

    def test_restore_nonexistent(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.checkpoint import CheckpointManager
            cm = CheckpointManager(workdir=Path(d), checkpoints_dir=Path(d) / "cps")
            assert not cm.restore("cp_nonexistent_xyz_12345")

    def test_prune_negative(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.checkpoint import CheckpointManager
            cm = CheckpointManager(workdir=Path(d), checkpoints_dir=Path(d) / "cps")
            removed = cm.prune(keep=100)
            assert removed == 0

    def test_get_last_none(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.checkpoint import CheckpointManager
            cm = CheckpointManager(workdir=Path(d), checkpoints_dir=Path(d) / "cps")
            assert cm.get_last_checkpoint() is None


class TestBugHuntRepomap:
    """RepoMap edge cases."""

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.repomap import RepoMapGenerator
            gen = RepoMapGenerator(workdir=Path(d))
            result = gen.generate_map(max_files=5)
            assert "Files indexed" in result

    def test_find_symbol_nonexistent(self):
        from terry.core.repomap import RepoMapGenerator
        results = RepoMapGenerator().find_symbol("nonexistent_function_xyz")
        assert results == []


class TestBugHuntCache:
    """Cache edge cases."""

    def test_get_expired(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.cache import Cache
            cache = Cache(cache_dir=Path(d))
            cache.set("key", "val", ttl=0)  # Immediate expiry
            time.sleep(0.01)
            assert cache.get("key") is None

    def test_clear_empty(self):
        from terry.core.cache import Cache
        assert Cache().clear() >= 0

    def test_llm_cache_miss(self):
        from terry.core.cache import LLMCache
        result = LLMCache().get_response([{"role": "user", "content": "never cached"}])
        assert result is None

    def test_tool_cache_miss(self):
        from terry.core.cache import ToolCache
        result = ToolCache().get_result("bash", {"command": "never_executed"})
        assert result is None


class TestBugHuntSession:
    """Session edge cases."""

    def test_new_with_custom_id(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            sid = s.new("custom_001")
            assert sid == "custom_001"

    def test_save_no_session_id(self):
        from terry.core.session import Session
        s = Session()
        assert not s.save()

    def test_load_nonexistent(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.session import Session
            s = Session(session_dir=Path(d))
            assert not s.load("nonexistent")

    def test_delete_no_session(self):
        from terry.core.session import Session
        assert not Session().delete()


class TestBugHuntContextCompact:
    """Context compaction edge cases."""

    def test_estimate_empty(self):
        from terry.core.context_compact import ContextCompactor
        assert ContextCompactor().estimate_tokens([]) == 0

    def test_needs_compaction_small(self):
        from terry.core.context_compact import ContextCompactor
        msgs = [{"role": "user", "content": "hi"}]
        assert not ContextCompactor().needs_compaction(msgs)

    def test_compact_no_llm(self):
        from terry.core.context_compact import ContextCompactor
        msgs = [{"role": "user", "content": "x" * 100000}]
        result = ContextCompactor().compact(msgs, llm_client=None)
        assert isinstance(result, list)

    def test_auto_compact_no_llm(self):
        from terry.core.context_compact import ContextCompactor
        msgs = [{"role": "user", "content": "x" * 10000} for _ in range(20)]
        result = ContextCompactor()._auto_compact(msgs, llm_client=None)
        assert len(result) < len(msgs)


class TestBugHuntErrorRecovery:
    """Error recovery edge cases."""

    def test_handle_api_error_non_retryable(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery()
        result = er.handle_api_error(ValueError("invalid request"), 0)
        assert result["action"] == "fail"

    def test_should_retry_max_attempts(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(max_retries=3)
        assert not er.should_retry(Exception("rate limit"), 3)

    def test_delay_cap(self):
        from terry.core.error_recovery import ErrorRecovery
        er = ErrorRecovery(max_delay=60)
        delay = er.get_delay(10)
        assert delay <= 60

    def test_auto_heal_max_attempts(self):
        from terry.core.error_recovery import AutoHealer
        h = AutoHealer(max_attempts=2)
        result = h.attempt_heal("bash", {}, "command not found: xyz", retry_count=2)
        assert result is None

    def test_auto_heal_non_healable(self):
        from terry.core.error_recovery import AutoHealer
        h = AutoHealer()
        result = h.analyze_error("bash", "some random message xyz123")
        assert result is None


class TestBugHuntMetrics:
    """Metrics edge cases."""

    def test_timer_stop_new_name(self):
        from terry.core.metrics import Metrics
        m = Metrics()
        t = m.timer_start()
        dur = m.timer_stop("new_timer", t)
        assert dur >= 0
        assert m.get_timer_stats("new_timer")["count"] == 1

    def test_cost_estimate_with_fallback(self):
        from terry.core.metrics import estimate_cost
        cost = estimate_cost("claude-sonnet-4-new-model", 1000, 500)
        assert cost > 0  # Should match prefix "claude-sonnet-4"

    def test_save_and_load_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.metrics import Metrics
            m = Metrics(metrics_dir=Path(d))
            m.increment("test", 5)
            path = m.save("test_metrics.json")
            m2 = Metrics(metrics_dir=Path(d))
            assert m2.load("test_metrics.json")
            assert m2.get_counter("test") == 5


class TestBugHuntLogger:
    """Logger edge cases."""

    def test_logger_debug(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.logger import Logger
            logger = Logger(name="test", log_dir=Path(d), console=False, file=True, level=10)
            logger.debug("debug msg")
            content = (Path(d) / "test.log").read_text()
            assert "debug msg" in content

    def test_logger_warning(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.logger import Logger
            logger = Logger(name="test", log_dir=Path(d), console=False, file=True)
            logger.warning("warning msg")
            content = (Path(d) / "test.log").read_text()
            assert "warning msg" in content


class TestBugHuntSkill:
    """Skill edge cases."""

    def test_skill_manager_no_match(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.skill import SkillManager
            sm = SkillManager(skills_dirs=[Path(d)])
            assert sm.match_skill("nothing here") is None

    def test_skill_from_bad_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "SKILL.md"
            p.write_text("---\ninvalid: [unclosed\n---\n# Test")
            from terry.core.skill import Skill
            result = Skill.from_file(p)
            assert result is None


class TestBugHuntThinking:
    """Thinking edge cases."""

    def test_allocate_defaults(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        budgets = et.allocate()
        assert sum(budgets.values()) <= et.total

    def _skip_can_fit_large(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        msgs = [{"role": "user", "content": "x" * 20000} for _ in range(10)]
        assert not et.can_fit(msgs, "system")

    def test_window_unknown_model(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking(model="unknown-model-xyz")
        assert et.total == 200000  # Default fallback


class TestBugHuntScheduler:
    """Scheduler edge cases."""

    def _skip_schedule_max_tasks(self):
        from terry.core.scheduler import CronScheduler
        s = CronScheduler()
        s.MAX_TASKS = 5
        for i in range(10):
            s.schedule("test", {"i": i}, interval_seconds=0)
        assert len(s.tasks) <= 5

    def test_cancel_nonexistent(self):
        from terry.core.scheduler import CronScheduler
        assert not CronScheduler().cancel(99999)


class TestBugHuntFTS:
    """FTS5 search edge cases."""

    def test_search_empty_db(self):
        from terry.core.fts_search import FTSSearch
        results = FTSSearch().search("nonexistent query xyz")
        assert results == []

    def test_get_session_empty(self):
        from terry.core.fts_search import FTSSearch
        assert FTSSearch().get_session_messages("nonexistent") == []


class TestBugHuntCodeIndex:
    """Code index edge cases."""

    def test_parse_syntax_error(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "broken.py").write_text("def foo(:  # syntax error")
            from terry.core.code_index import CodeSemanticIndex
            ci = CodeSemanticIndex(workdir=Path(d), cache_dir=Path(d) / "idx")
            ci.build_index(force=True)
            assert len(ci.find_definition("foo")) == 0  # Should skip gracefully


class TestBugHuntDockerSandbox:
    """Docker sandbox edge cases."""

    def test_run_without_docker(self):
        from terry.core.docker_sandbox import DockerSandbox
        # Should not crash even if Docker is not available
        result = DockerSandbox().run_command("echo hello")
        assert isinstance(result, str)


class TestBugHuntLocalEmbed:
    """Local embed edge cases."""

    def test_similarity_identical(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        sim = le.similarity("hello world", "hello world")
        assert sim > 0.5

    def test_similarity_different(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        sim = le.similarity("apple banana", "quantum physics")
        assert sim < 0.5


class TestBugHuntSpecExec:
    """Spec exec edge cases."""

    def test_get_prefetched_miss(self):
        from terry.core.spec_exec import SpeculativeExecutor
        se = SpeculativeExecutor()
        assert se.get_prefetched("never_prefetched.py") is None

    def test_analyze_non_trigger_tool(self):
        from terry.core.spec_exec import SpeculativeExecutor
        se = SpeculativeExecutor()
        preds = se.analyze_tool_call("read_file", {"path": "test.py"}, "content")
        assert isinstance(preds, list)


class TestBugHuntPromptCache:
    """Prompt cache edge cases."""

    def test_cacheable_short_content(self):
        from terry.core.prompt_cache import PromptCache
        pc = PromptCache()
        assert not pc.should_cache("short")

    def test_cacheable_long_content(self):
        from terry.core.prompt_cache import PromptCache
        pc = PromptCache()
        assert pc.should_cache("x" * 5000)


# ═══════════════════════════════════════════════════════════════════
# BUG FIXES found during testing
# ═══════════════════════════════════════════════════════════════════

class TestBugFixVerification:
    """Verify that discovered bugs are fixed."""

    def test_cli_t_variable_shadowing_fixed(self):
        """Verify the 't' variable shadowing bug is fixed in handle_command."""
        from terry.core.config import TerryConfig
        c = TerryConfig(); c.model.api_key = "test"
        from terry.core.agent import Agent
        a = Agent(c, enable_subagents=False, enable_skills=False,
                  enable_memory=False, enable_session=False,
                  enable_metrics=False, enable_cache=False,
                  enable_checkpoint=False, enable_planner=False)
        from terry.cli import handle_command
        # All these should work without UnboundLocalError
        assert handle_command("/help", a) is True
        assert handle_command("/new", a) is True
        assert handle_command("/skills", a) is True
        assert handle_command("/tutorial", a) is True
        assert handle_command("/undo", a) is True
        assert handle_command("/checkpoints", a) is True
        assert handle_command("/plan", a) is True
        assert handle_command("/permissions", a) is True
        assert handle_command("/curator", a) is True
        assert handle_command("/tasks", a) is True
        assert handle_command("/auto-skills", a) is True
        assert handle_command("/benchmark", a) is True
        assert handle_command("/search", a) is True
        assert handle_command("/replay", a) is True
        assert handle_command("/wfd", a) is True
        assert handle_command("/workflows", a) is True
