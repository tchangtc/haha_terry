"""Tests for cross-provider, user-configurable model fallback on overload.

Covers ErrorRecovery.should_fallback_model (same- and cross-provider), the
"provider:model" entry parser, user-configured chains, and the recovery wrapper
that switches the live client when the primary model is overloaded (529).
"""

from __future__ import annotations

import pytest

from terry.core.error_recovery import (
    FALLBACK_MODELS,
    ErrorRecovery,
    wrap_llm_call_with_recovery,
)

SONNET = "claude-sonnet-4-6-20250922"
HAIKU = "claude-haiku-3-5-20241022"


class TestResolveEntry:
    def test_cross_provider_entry(self):
        assert ErrorRecovery._resolve_entry("openai:gpt-4o", "anthropic") == ("openai", "gpt-4o")

    def test_same_provider_entry(self):
        assert ErrorRecovery._resolve_entry(HAIKU, "anthropic") == ("anthropic", HAIKU)

    def test_ollama_tag_not_mis_split(self):
        # "llama3:8b" is a model tag, not "provider:model" — prefix isn't a provider.
        assert ErrorRecovery._resolve_entry("llama3:8b", "ollama") == ("ollama", "llama3:8b")

    def test_cross_provider_with_ollama_tag(self):
        assert ErrorRecovery._resolve_entry("ollama:llama3:8b", "anthropic") == ("ollama", "llama3:8b")


class TestShouldFallbackModel:
    def _er(self, **kw):
        return ErrorRecovery(consecutive_529_limit=1, **kw)

    def test_no_fallback_before_limit(self):
        er = ErrorRecovery(consecutive_529_limit=3)
        assert er.should_fallback_model("anthropic", SONNET) is None  # 1st 529
        assert er.should_fallback_model("anthropic", SONNET) is None  # 2nd 529

    def test_same_provider_first(self):
        er = self._er()
        assert er.should_fallback_model("anthropic", SONNET) == ("anthropic", HAIKU)

    def test_cross_provider_when_same_exhausted(self, monkeypatch):
        # Primary is already the haiku model → first anthropic entry is skipped,
        # so it crosses over to OpenAI (whose key is available here).
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        er = self._er()
        assert er.should_fallback_model("anthropic", HAIKU) == ("openai", "gpt-4o")

    def test_cross_provider_skipped_without_credentials(self, monkeypatch):
        # No OpenAI/DeepSeek keys → both cross-provider entries are skipped,
        # and the only same-provider entry equals the current model → no fallback.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        er = self._er()
        assert er.should_fallback_model("anthropic", HAIKU) is None

    def test_disabled_returns_none(self):
        er = ErrorRecovery(consecutive_529_limit=1, model_fallback=False)
        assert er.should_fallback_model("anthropic", SONNET) is None

    def test_unknown_provider_has_no_chain(self):
        er = self._er()
        assert er.should_fallback_model("no-such-provider", "x") is None

    def test_user_fallbacks_take_priority(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        er = ErrorRecovery(consecutive_529_limit=1, user_fallbacks=["deepseek:deepseek-chat"])
        # User chain wins over built-in anthropic defaults.
        assert er.should_fallback_model("anthropic", SONNET) == ("deepseek", "deepseek-chat")

    def test_counter_resets_after_fallback(self):
        er = self._er()
        er.should_fallback_model("anthropic", SONNET)
        assert er._consecutive_529_count["anthropic:" + SONNET] == 0

    def test_reset_fallback_clears_state(self):
        er = self._er()
        er.should_fallback_model("anthropic", SONNET)
        er._active_fallback = "x"
        er.reset_fallback()
        assert er._active_fallback is None
        assert er._consecutive_529_count == {}


class TestDefaultsAreCrossProvider:
    def test_every_provider_chain_has_a_cross_provider_entry(self):
        for provider, chain in FALLBACK_MODELS.items():
            assert any(":" in e for e in chain), f"{provider} has no cross-provider fallback"

    def test_no_legacy_model_ids(self):
        flat = [e for chain in FALLBACK_MODELS.values() for e in chain]
        assert "claude-3-5-sonnet-20241022" not in flat
        assert "gpt-3.5-turbo" not in flat


class TestRecoveryWrapperFallback:
    def _er(self):
        return ErrorRecovery(consecutive_529_limit=1, max_retries=5, base_delay=0.0)

    def test_success_path_resets(self):
        er = self._er()
        wrapped = wrap_llm_call_with_recovery(lambda m, **k: {"ok": 1}, er)
        assert wrapped([]) == {"ok": 1}

    def test_overload_triggers_fallback_then_succeeds(self):
        er = self._er()
        state = {"n": 0}
        switches: list[tuple[str, str]] = []

        def flaky(messages, **kw):
            state["n"] += 1
            if state["n"] == 1:
                raise Exception("Error 529 overloaded")
            return {"ok": True}

        wrapped = wrap_llm_call_with_recovery(
            flaky, er, provider="anthropic", model=SONNET,
            on_fallback=lambda p, m: switches.append((p, m)),
        )
        assert wrapped([]) == {"ok": True}
        assert switches == [("anthropic", HAIKU)]

    def test_overload_without_callback_does_not_switch(self):
        # No on_fallback → behaves as retry; a persistent failure exhausts retries.
        er = ErrorRecovery(consecutive_529_limit=1, max_retries=2, base_delay=0.0)

        def always_overloaded(messages, **kw):
            raise Exception("529 overloaded")

        wrapped = wrap_llm_call_with_recovery(always_overloaded, er)
        with pytest.raises(Exception):
            wrapped([])

    def test_non_retryable_error_raises_immediately(self):
        er = self._er()
        calls = {"n": 0}

        def bad_auth(messages, **kw):
            calls["n"] += 1
            raise Exception("Invalid API key")

        wrapped = wrap_llm_call_with_recovery(
            bad_auth, er, provider="anthropic", model=SONNET, on_fallback=lambda p, m: None
        )
        with pytest.raises(Exception, match="Invalid API key"):
            wrapped([])
        assert calls["n"] == 1  # not retried


class TestConfigFallbackModels:
    def test_roundtrip_through_dict(self, tmp_path):
        from terry.core.config import TerryConfig

        cfg = TerryConfig()
        cfg.model.fallback_models = ["claude-haiku-3-5-20241022", "openai:gpt-4o"]
        path = tmp_path / "terry.json"
        cfg.save(str(path))
        loaded = TerryConfig.load(str(path))
        assert loaded.model.fallback_models == ["claude-haiku-3-5-20241022", "openai:gpt-4o"]

    def test_default_is_empty_list(self):
        from terry.core.config import ModelConfig

        assert ModelConfig().fallback_models == []


class TestProviderUsable:
    def test_known_provider_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert ErrorRecovery._provider_usable("openai") is True

    def test_known_provider_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert ErrorRecovery._provider_usable("openai") is False

    def test_keyless_provider_always_usable(self):
        # Ollama runs locally and needs no API key.
        assert ErrorRecovery._provider_usable("ollama") is True

    def test_unknown_provider_not_usable(self):
        assert ErrorRecovery._provider_usable("no-such-provider") is False


class TestAgentRestoresPrimaryAfterFallback:
    """F1 guard: a transient overload must not pin the session to the fallback."""

    def test_primary_restored_after_fallback(self, monkeypatch):
        from terry.core.agent import Agent
        from terry.core.config import TerryConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        cfg = TerryConfig()
        cfg.model.api_key = "test"
        cfg.model.provider = "anthropic"
        cfg.model.model = SONNET
        agent = Agent(
            cfg, enable_memory=False, enable_session=False, enable_metrics=False,
            enable_cache=False, enable_subagents=False, enable_skills=False,
            enable_checkpoint=False, enable_planner=False,
        )
        agent.error_recovery.consecutive_529_limit = 1  # fall back on first overload

        reconfigures: list[tuple[str, str]] = []
        monkeypatch.setattr(
            agent.llm, "reconfigure", lambda c: reconfigures.append((c.provider, c.model))
        )
        state = {"n": 0}

        def fake_chat(messages, **kw):
            state["n"] += 1
            if state["n"] == 1:
                raise Exception("Error 529 overloaded")
            return {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}

        monkeypatch.setattr(agent.llm, "chat", fake_chat)
        agent.messages = [{"role": "user", "content": "hi"}]

        result = agent._call_llm("system", [])

        assert result is not None
        # Switched to the same-provider haiku fallback, then restored to primary.
        assert reconfigures[0] == ("anthropic", HAIKU)
        assert reconfigures[-1] == ("anthropic", SONNET)


def _agent(monkeypatch, **model_over):
    from terry.core.agent import Agent
    from terry.core.config import TerryConfig

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    cfg = TerryConfig()
    cfg.model.api_key = "test"
    cfg.model.provider = "anthropic"
    cfg.model.model = SONNET
    for k, v in model_over.items():
        setattr(cfg.model, k, v)
    agent = Agent(
        cfg, enable_memory=False, enable_session=False, enable_metrics=False,
        enable_cache=False, enable_subagents=False, enable_skills=False,
        enable_checkpoint=False, enable_planner=False,
    )
    agent.error_recovery.consecutive_529_limit = 1
    return agent


def _overload_once_chat():
    st = {"n": 0}

    def chat(messages, **kw):
        st["n"] += 1
        if st["n"] == 1:
            raise Exception("Error 529 overloaded")
        return {"content": [{"type": "text", "text": "ok"}]}

    return chat


class TestReviewFixes:
    """Regression guards for the 4 issues found in adversarial review."""

    def test_f1_same_provider_fallback_preserves_base_url(self, monkeypatch):
        # A same-provider fallback must keep the user's custom base_url (proxy),
        # not re-derive the vendor default.
        agent = _agent(monkeypatch, base_url="https://my-proxy.example/v1")
        captured: list[tuple[str, str, str]] = []
        monkeypatch.setattr(
            agent.llm, "reconfigure",
            lambda c: captured.append((c.provider, c.model, c.base_url)),
        )
        monkeypatch.setattr(agent.llm, "chat", _overload_once_chat())
        agent.messages = [{"role": "user", "content": "hi"}]

        agent._call_llm("system", [])

        assert captured[0] == ("anthropic", HAIKU, "https://my-proxy.example/v1")

    def test_f2_fallback_called_when_limit_ge_max_retries(self):
        # consecutive_529_limit (4) >= max_retries (3): the switched model must
        # still get a real call rather than being stranded past the loop bound.
        er = ErrorRecovery(consecutive_529_limit=4, max_retries=3, base_delay=0.0)
        switches: list[tuple[str, str]] = []
        st = {"n": 0}

        def flaky(messages, **kw):
            st["n"] += 1
            if st["n"] <= 4:
                raise Exception("Error 529 overloaded")
            return {"ok": True}

        wrapped = wrap_llm_call_with_recovery(
            flaky, er, provider="anthropic", model=SONNET,
            on_fallback=lambda p, m: switches.append((p, m)),
        )
        assert wrapped([]) == {"ok": True}
        assert switches == [("anthropic", HAIKU)]

    def test_f3_reconfigure_failure_still_restores_primary(self, monkeypatch):
        # If building the fallback client raises, the finally-block must still
        # restore the primary — not leave the session pinned to a broken client.
        agent = _agent(monkeypatch)
        calls: list[tuple[str, str]] = []

        def recon(c):
            calls.append((c.provider, c.model))
            if c.model == HAIKU:
                raise RuntimeError("client build failed")

        monkeypatch.setattr(agent.llm, "reconfigure", recon)

        def always_overloaded(messages, **kw):
            raise Exception("Error 529 overloaded")

        monkeypatch.setattr(agent.llm, "chat", always_overloaded)
        agent.messages = [{"role": "user", "content": "hi"}]

        result = agent._call_llm("system", [])

        assert result is None  # the call ultimately failed
        assert ("anthropic", SONNET) in calls  # ...but primary was restored

    def test_f4_counter_resets_after_non_overload_error(self):
        er = ErrorRecovery(consecutive_529_limit=5, max_retries=5, base_delay=0.0)
        seq = iter(["Error 529 overloaded", "Invalid API key"])

        def flaky(messages, **kw):
            raise Exception(next(seq))

        wrapped = wrap_llm_call_with_recovery(
            flaky, er, provider="anthropic", model=SONNET, on_fallback=lambda p, m: None
        )
        with pytest.raises(Exception, match="Invalid API key"):
            wrapped([])
        # The non-529 error broke the streak → no stale count leaks to later calls.
        assert er._consecutive_529_count == {}

    def test_persistent_overload_terminates_without_pingpong(self, monkeypatch):
        # limit=1 + credentialed cross-provider chains could ping-pong forever;
        # `tried` must bound switches so this returns instead of hanging.
        for key in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
            monkeypatch.setenv(key, "sk-test")
        er = ErrorRecovery(consecutive_529_limit=1, max_retries=3, base_delay=0.0)
        switches: list[tuple[str, str]] = []

        def always_overloaded(messages, **kw):
            raise Exception("Error 529 overloaded")

        wrapped = wrap_llm_call_with_recovery(
            always_overloaded, er, provider="anthropic", model=SONNET,
            on_fallback=lambda p, m: switches.append((p, m)),
        )
        with pytest.raises(Exception):
            wrapped([])
        # Bounded: each target switched to at most once, no cycles.
        assert len(switches) == len(set(switches))
        assert len(switches) <= 8
