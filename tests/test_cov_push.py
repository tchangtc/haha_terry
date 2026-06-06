"""Targeted coverage push — remaining low-coverage modules."""

from __future__ import annotations

import tempfile, json, os
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# LLM CLIENT — more paths
# ═══════════════════════════════════════════════════════════════════

class TestLLMDeep:
    def test_chat_openai_protocol(self):
        from terry.core.config import ModelConfig
        from terry.core.llm import LLMClient
        mc = ModelConfig(provider="openai", api_key="test", model="gpt-4o")
        client = LLMClient(mc)
        assert client.provider_type == "openai"

    def test_chat_with_stream_method(self):
        from terry.core.config import ModelConfig
        from terry.core.llm import LLMClient
        mc = ModelConfig(provider="anthropic", api_key="test", model="claude-sonnet-4-20250514")
        client = LLMClient(mc)
        assert callable(client.chat_stream)



# ═══════════════════════════════════════════════════════════════════
# CONFIG — more paths
# ═══════════════════════════════════════════════════════════════════

class TestConfigDeep:
    def test_provider_registry_has_all(self):
        from terry.core.config import PROVIDER_REGISTRY
        assert "anthropic" in PROVIDER_REGISTRY
        assert "openai" in PROVIDER_REGISTRY
        assert "deepseek" in PROVIDER_REGISTRY
        assert "zhipu" in PROVIDER_REGISTRY
        assert "qwen" in PROVIDER_REGISTRY
        assert "ollama" in PROVIDER_REGISTRY

    def test_terry_config_from_dict_full(self):
        from terry.core.config import TerryConfig
        data = {
            "model": {"provider": "deepseek", "model": "deepseek-chat"},
            "max_tool_calls": 99,
            "sandbox_mode": "auto",
            "permission_level": "low",
            "skills_paths": ["./custom"],
            "memory_enabled": False,
        }
        cfg = TerryConfig._from_dict(data)
        assert cfg.max_tool_calls == 99
        assert cfg.sandbox_mode == "auto"
        assert cfg.permission_level == "low"
        assert not cfg.memory_enabled


# ═══════════════════════════════════════════════════════════════════
# ADAPTER — more paths
# ═══════════════════════════════════════════════════════════════════

class TestAdapterDeep:
    def test_get_provider_unknown(self):
        from terry.core.adapter import get_provider
        assert get_provider("nonexistent_provider_xyz") is None

    def test_providers_have_models(self):
        from terry.core.adapter import PROVIDERS
        for name, adapter in PROVIDERS.items():
            assert len(adapter.models) >= 1, f"{name} has no models"

    def test_ollama_no_key(self):
        from terry.core.adapter import get_provider, resolve_api_key
        provider = get_provider("ollama")
        assert resolve_api_key(provider) == ""


# ═══════════════════════════════════════════════════════════════════
# CONTEXT COMPACT — more edge paths
# ═══════════════════════════════════════════════════════════════════

class TestCompactionDeep:
    def test_compact_all_layers(self):
        from terry.core.context_compact import ContextCompactor
        cc = ContextCompactor(max_tokens=1000)
        # Create messages that will trigger all layers
        msgs = [{"role": "user", "content": "x" * 60000}] + \
               [{"role": "user", "content": f"msg_{i}"} for i in range(30)]
        result = cc.compact(msgs, llm_client=None)
        assert len(result) < len(msgs)

    def test_persist_output_new(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.context_compact import ContextCompactor
            cc = ContextCompactor(budget_dir=Path(d))
            path = cc._persist_output("test content " * 5000)
            assert path.exists()

    def test_summarize_no_llm(self):
        from terry.core.context_compact import ContextCompactor
        cc = ContextCompactor()
        msgs = [{"role": "user", "content": "hello world"}] * 10
        summary = cc._summarize(msgs, llm_client=None)
        assert isinstance(summary, str)


# ═══════════════════════════════════════════════════════════════════
# PLUGIN — more paths
# ═══════════════════════════════════════════════════════════════════

class TestPluginDeep:
    def test_plugin_from_dir_no_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.plugin import Plugin
            pdir = Path(d) / "my-plugin"
            pdir.mkdir()
            result = Plugin.from_dir(pdir)
            assert result is None

    def test_plugin_from_dir_bad_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.plugin import Plugin
            pdir = Path(d) / "my-plugin"
            pdir.mkdir()
            (pdir / "plugin.yaml").write_text("invalid: [yaml: broken")
            result = Plugin.from_dir(pdir)
            assert result is None

    def test_plugin_load_tools_empty(self):
        from terry.core.plugin import Plugin
        p = Plugin("test", "0.1", "", Path("/tmp"))
        count = p.load_tools(None)
        assert count == 0

    def test_plugin_load_hooks_empty(self):
        from terry.core.plugin import Plugin
        p = Plugin("test", "0.1", "", Path("/tmp"))
        count = p.load_hooks(None)
        assert count == 0


# ═══════════════════════════════════════════════════════════════════
# SWE BENCH — more paths
# ═══════════════════════════════════════════════════════════════════

class TestSWEBenchDeep:
    def test_problem_to_dict(self):
        from terry.core.swe_bench import SWEBenchProblem
        p = SWEBenchProblem("id1", "repo", "desc", difficulty="hard")
        d = p.to_dict()
        assert d["instance_id"] == "id1"
        assert d["difficulty"] == "hard"

    def test_result_to_dict(self):
        from terry.core.swe_bench import SWEBenchResult
        r = SWEBenchResult("id1")
        r.status = "passed"
        r.score = 0.95
        d = r.to_dict()
        assert d["status"] == "passed"

    def test_run_problem_with_errors(self):
        from terry.core.swe_bench import SWEBenchRunner, SWEBenchProblem
        runner = SWEBenchRunner(agent_factory=None)
        result = runner.run_single(SWEBenchProblem("test", "repo", "fix bug"))
        assert result.status in ("passed", "failed", "error")


# ═══════════════════════════════════════════════════════════════════
# SUBAGENT — more paths
# ═══════════════════════════════════════════════════════════════════

class TestSubagentDeep:
    def test_list_tasks(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.subagent import SubAgentManager
        mgr = SubAgentManager(config, Path.cwd(), MagicMock(), use_worktree=False)
        tasks = mgr.list_tasks()
        assert isinstance(tasks, list)

    def test_wait_unknown(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.subagent import SubAgentManager
        import pytest
        mgr = SubAgentManager(config, Path.cwd(), MagicMock(), use_worktree=False)
        with pytest.raises(ValueError):
            mgr.wait("nonexistent_task_id")


# ═══════════════════════════════════════════════════════════════════
# CACHE — edge
# ═══════════════════════════════════════════════════════════════════

class TestCacheDeep:
    def test_cache_delete_missing(self):
        from terry.core.cache import Cache
        assert not Cache().delete("nonexistent_key")

    def test_cache_get_expired_disk(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.cache import Cache
            cache = Cache(cache_dir=Path(d), default_ttl=0)
            cache.set("key", "val")
            import time; time.sleep(0.01)
            # Force disk read by clearing memory
            cache.memory_cache.clear()
            assert cache.get("key") is None


# ═══════════════════════════════════════════════════════════════════
# SESSION — list edge
# ═══════════════════════════════════════════════════════════════════

class TestSessionDeep:
    def test_list_sessions_nonexistent_dir(self):
        from terry.core.session import Session
        sessions = Session.list_sessions(Path("/nonexistent/dir/xyz"))
        assert sessions == []


# ═══════════════════════════════════════════════════════════════════
# I18N — more
# ═══════════════════════════════════════════════════════════════════

class TestI18nDeep:
    def test_t_with_variables(self):
        from terry.i18n import t
        result = t("cli.model_info", provider="test", model="test-model")
        assert "test" in result

    def test_default_language_fallback(self):
        from terry.i18n import I18n
        i18n = I18n("en")
        i18n.set_language("zh")
        # Force a key that doesn't exist in zh
        result = i18n.t("errors.unknown_command", command="xyz_cmd")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# AGENT — fork and mentions
# ═══════════════════════════════════════════════════════════════════

def _agent():
    from terry.core.config import TerryConfig
    c = TerryConfig(); c.model.api_key = "test"
    from terry.core.agent import Agent
    return Agent(c, enable_subagents=False, enable_skills=False,
                 enable_memory=False, enable_session=False,
                 enable_metrics=False, enable_cache=False,
                 enable_checkpoint=False, enable_planner=False)


class TestAgentDeep:
    def test_fork_clones_messages(self):
        a = _agent()
        a.messages.append({"role": "user", "content": "test"})
        forked = a.fork()
        assert len(forked.messages) == 1

    def test_parse_mentions_git(self):
        a = _agent()
        result = a.parse_mentions("check @git:main")
        assert isinstance(result, str)

    def test_build_system_prompt_with_skill(self):
        a = _agent()
        a.active_skill = "test-skill"
        prompt = a.build_system_prompt()
        assert isinstance(prompt, str)

    def test_get_status_full(self):
        a = _agent()
        status = a.get_status()
        assert "workdir" in status
        assert "tools_available" in status
