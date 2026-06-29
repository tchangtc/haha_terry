"""Tests for v2.x modules: plugin_ecosystem, agent_team, auto_pipeline, cost_tracker, model_discovery."""

from __future__ import annotations

import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# PLUGIN ECOSYSTEM
# ═══════════════════════════════════════════════════════════════════

class TestPluginEcosystem:
    def test_import(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        assert PluginEcosystem is not None

    def test_rate_and_get(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            eco = PluginEcosystem(data_dir=Path(d))
            eco.rate("p1", 5)
            eco.rate("p1", 4)
            r = eco.get_rating("p1")
            assert r.average == 4.5
            assert r.total_ratings == 2

    def test_rate_clamping(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            eco = PluginEcosystem(data_dir=Path(d))
            eco.rate("x", 10)
            assert eco.get_rating("x").average == 5.0
            eco.rate("y", -1)
            assert eco.get_rating("y").average == 1.0

    def test_review_and_get(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            eco = PluginEcosystem(data_dir=Path(d))
            eco.review("p1", "Great!", 5, "alice")
            reviews = eco.get_reviews("p1")
            assert len(reviews) == 1
            assert reviews[0].author == "alice"

    def test_submission_workflow(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            eco = PluginEcosystem(data_dir=Path(d))
            eco.submit_plugin("cool", "github.com/x", "bob")
            assert len(eco.get_submissions("pending")) == 1
            eco.review_submission(0, True, "mod")
            assert len(eco.get_submissions("published")) == 1
            assert eco.get_submissions("published")[0]["name"] == "cool"

    def test_persistence(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            eco1 = PluginEcosystem(data_dir=p)
            eco1.rate("p1", 5)
            eco2 = PluginEcosystem(data_dir=p)
            assert eco2.get_rating("p1").total_ratings == 1

    def test_stats(self):
        from terry.core.plugin_ecosystem import PluginEcosystem
        with tempfile.TemporaryDirectory() as d:
            eco = PluginEcosystem(data_dir=Path(d))
            eco.rate("p1", 5)
            eco.review("p1", "ok", 3, "alice")
            stats = eco.get_stats()
            assert stats["total_ratings"] == 1
            assert stats["total_reviews"] == 1


# ═══════════════════════════════════════════════════════════════════
# AGENT TEAM
# ═══════════════════════════════════════════════════════════════════

class TestAgentTeam:
    def test_import(self):
        from terry.core.agent_team import TeamRole
        assert TeamRole.ARCHITECT == "architect"

    def test_empty_team(self):
        from terry.core.agent_team import AgentTeam
        team = AgentTeam("test")
        results = team.execute()
        assert len(results) == 0

    def test_add_member(self):
        from terry.core.agent_team import AgentTeam, TeamRole
        team = AgentTeam("test")
        team.add_member("alice", TeamRole.ARCHITECT)
        assert len(team.get_members()) == 1
        assert team.get_members()[0].name == "alice"

    def test_remove_member(self):
        from terry.core.agent_team import AgentTeam, TeamRole
        team = AgentTeam("test")
        team.add_member("alice", TeamRole.ARCHITECT)
        team.remove_member("alice")
        assert len(team.get_members()) == 0

    def test_assign_and_execute(self):
        from terry.core.agent_team import AgentTeam, TeamRole
        team = AgentTeam("test")
        team.add_member("alice", TeamRole.ARCHITECT)
        tid = team.assign_task("design API", "alice", TeamRole.ARCHITECT)
        assert tid.startswith("task-")
        result = team.execute_round(tid)
        assert len(result) > 0  # passthrough mode

    def test_execute_pipeline(self):
        from terry.core.agent_team import AgentTeam, TeamRole
        team = AgentTeam("build API")
        team.add_member("a", TeamRole.ARCHITECT)
        team.add_member("d", TeamRole.DEVELOPER)
        team.add_member("r", TeamRole.REVIEWER)
        results = team.execute()
        assert "architecture" in results
        assert "implementation" in results
        assert "review" in results

    def test_stats(self):
        from terry.core.agent_team import AgentTeam, TeamRole
        team = AgentTeam("test")
        team.add_member("a", TeamRole.ARCHITECT)
        stats = team.get_stats()
        assert stats["members"] == 1
        assert stats["mission"] == "test"


# ═══════════════════════════════════════════════════════════════════
# AUTO PIPELINE
# ═══════════════════════════════════════════════════════════════════

class TestAutoPipeline:
    def test_import(self):
        from terry.core.auto_pipeline import PipelineStage
        assert len([s for s in PipelineStage]) == 7

    def test_pipeline_run(self):
        from terry.core.auto_pipeline import AutoPipeline
        pipe = AutoPipeline(auto_approve=True)
        result = pipe.run("test requirement")
        assert "summary" in result
        assert len(pipe.get_tasks()) == 6

    def test_pipeline_pause_resume(self):
        from terry.core.auto_pipeline import AutoPipeline
        pipe = AutoPipeline()
        pipe.pause()
        assert pipe.get_stats()["paused"]
        pipe.resume()
        assert not pipe.get_stats()["paused"]

    def test_pipeline_task_filtering(self):
        from terry.core.auto_pipeline import AutoPipeline, PipelineStage
        pipe = AutoPipeline(auto_approve=True)
        pipe.run("test")
        tasks = pipe.get_tasks(PipelineStage.DESIGN)
        assert len(tasks) == 1
        assert tasks[0].stage == PipelineStage.DESIGN


# ═══════════════════════════════════════════════════════════════════
# MODEL DISCOVERY
# ═══════════════════════════════════════════════════════════════════

class TestModelDiscovery:
    def test_import(self):
        from terry.core.model_discovery import discover_models
        assert callable(discover_models)

    def test_classify_tier(self):
        from terry.core.model_discovery import _classify_tier
        assert _classify_tier("llama3-8b") == "budget"
        assert _classify_tier("gpt-4o") == "medium"
        assert _classify_tier("claude-opus-4-8") == "premium"
        assert _classify_tier("some-model") == "medium"

    def test_guess_provider(self):
        from terry.core.model_discovery import _guess_provider
        assert _guess_provider("http://localhost:11434/v1") == "local"
        assert _guess_provider("https://api.openai.com/v1") == "openai"
        assert _guess_provider("https://api.deepseek.com/v1") == "deepseek"


# ═══════════════════════════════════════════════════════════════════
# COST TRACKER
# ═══════════════════════════════════════════════════════════════════

class TestCostTracker:
    def test_import(self):
        from terry.core.cost_tracker import CostTracker
        assert CostTracker is not None

    def test_record_and_summary(self):
        from terry.core.cost_tracker import CostTracker
        tracker = CostTracker(budget_usd=10.0)
        tracker.record_call("claude-sonnet-4-6", 500, 200)
        summary = tracker.get_summary()
        assert summary["total_calls"] == 1
        assert float(summary["total_cost"].replace("$", "")) > 0

    def test_budget_warning(self):
        from terry.core.cost_tracker import CostTracker
        tracker = CostTracker(budget_usd=0.001)
        tracker.record_call("claude-opus-4-8", 10000, 5000)
        summary = tracker.get_summary()
        assert len(summary["warnings"]) > 0

    def test_by_model_breakdown(self):
        from terry.core.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.record_call("claude-sonnet-4-6", 100, 50)
        tracker.record_call("claude-haiku-4-5", 200, 100)
        summary = tracker.get_summary()
        models = summary["by_model"]
        assert len(models) == 2

    def test_token_counts(self):
        from terry.core.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.record_call("gpt-4o", 300, 150)
        tokens = tracker.get_total_tokens()
        assert tokens["input"] == 300
        assert tokens["output"] == 150

    def test_reset_budget(self):
        from terry.core.cost_tracker import CostTracker
        tracker = CostTracker(budget_usd=5.0)
        tracker.reset_budget(20.0)
        assert tracker._budget == 20.0
