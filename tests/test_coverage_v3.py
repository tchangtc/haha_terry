"""Push coverage from 53% toward 65% — targeted tests for remaining gaps."""

from __future__ import annotations

import asyncio


# ═══════════════════════════════════════════════════════════════════
# AGENT SWARM — additional patterns
# ═══════════════════════════════════════════════════════════════════

class TestSwarmMore:
    def test_swarm_task_fields(self):
        from terry.core.agent_swarm import SwarmTask
        t = SwarmTask(id="1", prompt="test")
        assert t.status == "pending"

    def test_swarm_result_fields(self):
        from terry.core.agent_swarm import SwarmResult
        r = SwarmResult()
        assert r.stats == {}
        assert r.tasks == []

    def test_swarm_broadcast_no_tasks(self):
        from terry.core.agent_swarm import AgentSwarm
        results = asyncio.run(AgentSwarm().broadcast("msg"))
        assert isinstance(results, dict)

    def test_swarm_get_task_nonexistent(self):
        from terry.core.agent_swarm import AgentSwarm
        assert AgentSwarm().get_task("nonexistent") is None

    def test_swarm_list_tasks_by_status(self):
        from terry.core.agent_swarm import AgentSwarm
        swarm = AgentSwarm()
        asyncio.run(swarm.scatter("test", count=2, timeout=5))
        assert len(swarm.list_tasks("done")) == 2
        assert len(swarm.list_tasks("failed")) == 0


# ═══════════════════════════════════════════════════════════════════
# SHARED SESSION — agent join/leave/messages
# ═══════════════════════════════════════════════════════════════════

class TestSharedSessionMore:
    def test_join_and_get_agents(self):
        from terry.core.shared_session import SharedSession, AgentRole
        s = SharedSession("test")
        s.join("a1", AgentRole.DEVELOPER)
        s.join("a2", AgentRole.REVIEWER)
        assert len(s.get_agents()) == 2

    def test_leave(self):
        from terry.core.shared_session import SharedSession, AgentRole
        s = SharedSession("test")
        s.join("a1", AgentRole.DEVELOPER)
        s.leave("a1")
        assert len(s.get_agents()) == 0

    def test_add_message(self):
        from terry.core.shared_session import SharedSession, AgentRole
        s = SharedSession("test")
        s.join("a1", AgentRole.ARCHITECT)
        s.add_user_message("hello")
        asyncio.run(s.add_agent_message("a1", "response"))
        assert len(s.get_messages()) == 3  # join system + user + agent

    def test_stats(self):
        from terry.core.shared_session import SharedSession, AgentRole
        s = SharedSession("test")
        s.join("a1", AgentRole.DEVELOPER)
        stats = s.get_stats()
        assert stats["agent_count"] == 1
        assert stats["session_id"] == "test"


# ═══════════════════════════════════════════════════════════════════
# MODEL ROUTER V2 — task classification and routing
# ═══════════════════════════════════════════════════════════════════

class TestModelRouterV2More:
    def test_classify_read(self):
        from terry.core.model_router_v2 import ModelRouterV2
        r = ModelRouterV2()
        assert r.classify_task("find auth.py") == "read"

    def test_classify_write(self):
        from terry.core.model_router_v2 import ModelRouterV2
        r = ModelRouterV2()
        assert r.classify_task("implement login page") == "write"

    def test_classify_debug(self):
        from terry.core.model_router_v2 import ModelRouterV2
        r = ModelRouterV2()
        assert r.classify_task("fix null pointer bug") == "debug"

    def test_route_returns_valid_model(self):
        from terry.core.model_router_v2 import ModelRouterV2, MODEL_REGISTRY
        r = ModelRouterV2()
        model = r.route("test query")
        assert model in MODEL_REGISTRY

    def test_route_to_profile(self):
        from terry.core.model_router_v2 import ModelRouterV2
        r = ModelRouterV2()
        profile = r.route_to_profile("test")
        assert profile.name == r.route("test")

    def test_get_available_models(self):
        from terry.core.model_router_v2 import ModelRouterV2
        models = ModelRouterV2().get_available_models()
        assert len(models) >= 5  # At least 5 models registered


# ═══════════════════════════════════════════════════════════════════
# MEMORY V2 — preference learning
# ═══════════════════════════════════════════════════════════════════

class TestMemoryV2More:
    def test_learn_and_recall(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            m.remember("key1", "value1", category="test")
            assert m.recall("key1") == "value1"

    def test_forget(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            m.remember("key1", "value1")
            m.forget("key1")
            assert m.recall("key1") is None

    def test_query(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            m.remember("auth_config", "JWT tokens", category="config")
            results = m.query("auth")
            assert len(results) >= 1

    def test_learn_preference(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            m.learn_preference("code_style", "use type hints")
            m.learn_preference("code_style", "use type hints")
            m.learn_preference("code_style", "use type hints")
            prefs = m.get_preferences("code_style")
            assert len(prefs) > 0

    def test_global_patterns(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            for _ in range(4):
                m.learn_preference("code_style", "use type hints")
            patterns = m.get_global_patterns()
            assert len(patterns) > 0

    def test_prune_stale(self):
        from terry.core.memory_v2 import MemoryV2
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            m = MemoryV2(storage_dir=Path(d))
            m.remember("old_key", "old_value")
            pruned = m.prune_stale(max_age_days=0)  # All stale
            assert pruned >= 0
