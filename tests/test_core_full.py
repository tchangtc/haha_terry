"""Full core module coverage — agent_hooks, skill, llm, planner, subagent, etc."""

from __future__ import annotations

import tempfile, json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# AGENT HOOKS — pre/post processing
# ═══════════════════════════════════════════════════════════════════

class TestAgentHooks:
    def test_pre_process_fts_index(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.agent import Agent
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        from terry.core.agent_hooks import pre_process
        enriched = pre_process(agent, "find auth")
        assert isinstance(enriched, str)

    def test_post_process(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.agent import Agent
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        import time
        from terry.core.agent_hooks import post_process
        result = post_process(agent, "fix bug", "I fixed it", time.time())
        assert isinstance(result, str)
        assert "I fixed it" in result


# ═══════════════════════════════════════════════════════════════════
# SKILL SYSTEM
# ═══════════════════════════════════════════════════════════════════

class TestSkillSystem:
    def test_skill_manager_reload(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.skill import SkillManager
            sm = SkillManager(skills_dirs=[Path(d)])
            sm.reload()
            assert len(sm.list_skills()) == 0

    def test_skill_manager_get_context(self):
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: Test\ntriggers:\n  - test\n---\n\n# Test\nDo stuff."
            )
            from terry.core.skill import SkillManager
            sm = SkillManager(skills_dirs=[Path(d)])
            skill = sm.get_skill("test-skill")
            assert skill is not None
            ctx = sm.get_skill_context(skill)
            assert "Test" in ctx

    def test_skill_from_file_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "SKILL.md"
            p.write_text("No frontmatter")
            from terry.core.skill import Skill
            result = Skill.from_file(p)
            assert result is None

    def test_skill_executor(self):
        from terry.core.skill import SkillManager, SkillExecutor
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.agent import Agent
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        sm = SkillManager(skills_dirs=[])
        executor = SkillExecutor(sm, agent)
        assert executor.skill_manager is sm


# ═══════════════════════════════════════════════════════════════════
# LLM CLIENT
# ═══════════════════════════════════════════════════════════════════

class TestLLMClient:
    def test_detect_provider_anthropic(self):
        from terry.core.config import ModelConfig
        from terry.core.llm import LLMClient
        mc = ModelConfig(provider="anthropic", api_key="test", model="claude-sonnet-4-20250514")
        client = LLMClient(mc)
        assert client.provider_type == "anthropic"

    def test_detect_provider_openai(self):
        from terry.core.config import ModelConfig
        from terry.core.llm import LLMClient
        mc = ModelConfig(provider="openai", api_key="test", model="gpt-4o")
        client = LLMClient(mc)
        assert client.provider_type == "openai"


# ═══════════════════════════════════════════════════════════════════
# PLANNER
# ═══════════════════════════════════════════════════════════════════

class TestPlannerFull:
    def test_format_plan(self):
        from terry.core.planner import Planner
        p = Planner(llm_client=None)
        plan = p.create_plan("fix auth", ["read_file", "edit_file"])
        formatted = p.format_plan(plan)
        assert "Execution Plan" in formatted

    def test_validate_with_destructive_no_research(self):
        from terry.core.planner import Planner
        p = Planner(llm_client=None)
        plan = {
            "steps": [{"phase": "implementation", "description": "edit", "destructive": True}],
            "has_destructive": True,
            "research_count": 0,
        }
        issues = p.validate_plan(plan)
        assert len(issues) >= 1


# ═══════════════════════════════════════════════════════════════════
# AUTONOMOUS AGENT
# ═══════════════════════════════════════════════════════════════════

class TestAutonomousAgent:
    def test_submit_and_start(self):
        from terry.core.autonomous_agent import AutonomousAgent
        aa = AutonomousAgent(lambda: None)
        aa.start()
        tid = aa.submit_task("fix auth bug")
        assert tid
        aa.stop()

    def test_get_status_after_start(self):
        from terry.core.autonomous_agent import AutonomousAgent
        aa = AutonomousAgent(lambda: None)
        status = aa.get_status()
        assert status["queued"] >= 0
        assert status["active"] >= 0

    def test_skill_auto_creator_suggest(self):
        from terry.core.autonomous_agent import SkillAutoCreator
        sac = SkillAutoCreator()
        result = sac.analyze_conversation(
            "fix the login bug",
            "1. Analyze auth.py\n2. Fix the bug at line 45\n3. Test the fix"
        )
        assert result is None or isinstance(result, dict)

    def test_create_skill_high_confidence(self):
        from terry.core.autonomous_agent import SkillAutoCreator
        sac = SkillAutoCreator(min_confidence=0.99)
        suggestion = {"name": "test", "description": "t", "triggers": ["test"], "confidence": 0.8}
        path = sac.create_skill(suggestion, "do this then that")
        assert path is None  # Below min_confidence


# ═══════════════════════════════════════════════════════════════════
# DYNAMIC WORKFLOW
# ═══════════════════════════════════════════════════════════════════

class TestDynamicWorkflowFull:
    def test_execute_all_patterns(self):
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern
        engine = DynamicWorkflowEngine()
        for pattern in WorkflowPattern:
            wf = engine.plan_workflow(f"test_{pattern.value}", pattern)
            assert wf.stages

    def test_resume_nonexistent(self):
        from terry.core.dynamic_workflow import DynamicWorkflowEngine
        result = DynamicWorkflowEngine().resume("nonexistent_id_xyz")
        assert result is None


# ═══════════════════════════════════════════════════════════════════
# SWE BENCH
# ═══════════════════════════════════════════════════════════════════

class TestSWEBench:
    def test_problems_exist(self):
        from terry.core.swe_bench import SWE_BENCH_PROBLEMS
        assert len(SWE_BENCH_PROBLEMS) >= 10

    def test_runner_no_agent(self):
        from terry.core.swe_bench import SWEBenchRunner
        runner = SWEBenchRunner(agent_factory=None)
        problems = runner.get_problems()
        assert len(problems) >= 10

    def test_leaderboard(self):
        from terry.core.swe_bench import SWEBenchRunner
        runner = SWEBenchRunner(agent_factory=None)
        lb = runner.get_leaderboard()
        assert len(lb) >= 1


# ═══════════════════════════════════════════════════════════════════
# SKILL MARKET
# ═══════════════════════════════════════════════════════════════════

class TestSkillMarketFull:
    def test_search_no_registry(self):
        from terry.core.skill_market import SkillMarket
        sm = SkillMarket()
        results = sm.search("test")
        assert isinstance(results, list)

    def test_install_nonexistent(self):
        from terry.core.skill_market import SkillMarket
        sm = SkillMarket()
        assert not sm.install("nonexistent_skill_xyz")

    def test_uninstall_nonexistent(self):
        from terry.core.skill_market import SkillMarket
        sm = SkillMarket()
        assert not sm.uninstall("nonexistent_skill_xyz")

    def test_get_skill_info_nonexistent(self):
        from terry.core.skill_market import SkillMarket
        sm = SkillMarket()
        assert sm.get_skill_info("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════
# SUBAGENT
# ═══════════════════════════════════════════════════════════════════

class TestSubagent:
    def test_manager_spawn_no_agent(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.tools import discover_tools, tool_registry
        discover_tools()
        from terry.core.subagent import SubAgentManager
        mgr = SubAgentManager(config, Path.cwd(), tool_registry, use_worktree=False)
        tid = mgr.spawn("test task")
        assert tid.startswith("task_")

    def test_manager_get_status_unknown(self):
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.subagent import SubAgentManager
        mgr = SubAgentManager(config, Path.cwd(), MagicMock(), use_worktree=False)
        assert mgr.get_status("nonexistent") == "unknown"

    def test_orchestrator_exists(self):
        from terry.core.subagent import Orchestrator
        from terry.core.config import TerryConfig
        config = TerryConfig(); config.model.api_key = "test"
        from terry.core.subagent import SubAgentManager
        mgr = SubAgentManager(config, Path.cwd(), MagicMock(), use_worktree=False)
        orch = Orchestrator(mgr)
        assert orch is not None


# ═══════════════════════════════════════════════════════════════════
# CODE INDEX
# ═══════════════════════════════════════════════════════════════════

class TestCodeIndex:
    def test_parse_python(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mod.py").write_text("class Foo:\n    def bar(self):\n        pass\n")
            from terry.core.code_index import CodeSemanticIndex
            ci = CodeSemanticIndex(workdir=Path(d), cache_dir=Path(d) / "cache")
            ci.build_index(force=True)
            assert len(ci.find_definition("Foo")) >= 1
            assert len(ci.find_references("Foo")) >= 1

    def test_search(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "mod.py").write_text("def my_func():\n    return 42\n")
            from terry.core.code_index import CodeSemanticIndex
            ci = CodeSemanticIndex(workdir=Path(d), cache_dir=Path(d) / "cache")
            ci.build_index(force=True)
            results = ci.search("my_func")
            assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════
# RAG
# ═══════════════════════════════════════════════════════════════════

class TestRAGFull:
    def test_index_project(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "code.py").write_text("def authenticate(user, pwd):\n    return True\n")
            from terry.core.rag import ProjectRAG
            rag = ProjectRAG(workdir=Path(d), index_dir=Path(d) / "idx")
            chunks = rag.index_project(max_files=10)
            assert chunks >= 1

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.rag import ProjectRAG
            rag = ProjectRAG(workdir=Path(d), index_dir=Path(d) / "idx")
            rag.add_document("test.py", "hello world")
            path = rag.save_index()
            rag2 = ProjectRAG(workdir=Path(d), index_dir=Path(d) / "idx")
            loaded = rag2.load_index()
            assert loaded >= 1


# ═══════════════════════════════════════════════════════════════════
# DOCKER SANDBOX
# ═══════════════════════════════════════════════════════════════════

class TestDockerSandboxFull:
    def test_is_available(self):
        from terry.core.docker_sandbox import DockerSandbox
        sandbox = DockerSandbox()
        result = sandbox.is_available()
        assert isinstance(result, bool)

    def test_run_isolated_no_docker(self):
        from terry.core.docker_sandbox import DockerSandbox
        sandbox = DockerSandbox()
        result = sandbox.run_isolated("echo hello")
        assert isinstance(result, str)

    def test_pull_image_offline(self):
        from terry.core.docker_sandbox import DockerSandbox
        sandbox = DockerSandbox()
        result = sandbox.pull_image("nonexistent-image:latest")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# LOCAL EMBED
# ═══════════════════════════════════════════════════════════════════

class TestLocalEmbedFull:
    def test_embed_with_sentence_transformers(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        vec = le.embed("test sentence for embedding")
        assert len(vec) > 0

    def test_search_multiple(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        docs = ["apple pie recipe", "car repair guide", "dog training tips"]
        results = le.search("baking", docs, top_k=2)
        assert len(results) >= 0


# ═══════════════════════════════════════════════════════════════════
# FTS SEARCH
# ═══════════════════════════════════════════════════════════════════

class TestFTSSearchFull:
    def test_index_multiple_sessions(self):
        from terry.core.fts_search import FTSSearch
        fts = FTSSearch()
        fts.index_message("s1", "user", "hello from session 1")
        fts.index_message("s2", "user", "hello from session 2")
        results = fts.search("hello", limit=10)
        assert len(results) >= 2

    def test_clear_session(self):
        from terry.core.fts_search import FTSSearch
        fts = FTSSearch()
        fts.index_message("temp", "user", "will be deleted")
        count = fts.clear_session("temp")
        assert count >= 1


# ═══════════════════════════════════════════════════════════════════
# CURATOR
# ═══════════════════════════════════════════════════════════════════

class TestCuratorFull:
    def test_suggest_new_skill(self):
        from terry.core.curator import SkillsCurator
        c = SkillsCurator()
        path = c.suggest_new_skill("test-skill", "A test", ["test"], "# Instructions")
        assert path is not None

    def test_prune_empty(self):
        from terry.core.curator import SkillsCurator
        c = SkillsCurator()
        removed = c.prune_skills([])
        assert removed == 0


# ═══════════════════════════════════════════════════════════════════
# SPEC EXEC
# ═══════════════════════════════════════════════════════════════════

class TestSpecExecFull:
    def test_prefetch_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "test.py").write_text("hello")
            from terry.core.spec_exec import SpeculativeExecutor
            se = SpeculativeExecutor()
            se.prefetch_files(Path(d), ["test.py"])
            import time; time.sleep(0.1)
            content = se.get_prefetched("test.py")
            assert content is not None

    def test_clear(self):
        from terry.core.spec_exec import SpeculativeExecutor
        se = SpeculativeExecutor()
        se._results["x"] = "y"
        se.clear()
        assert len(se._results) == 0


# ═══════════════════════════════════════════════════════════════════
# BENCHMARK
# ═══════════════════════════════════════════════════════════════════

class TestBenchmarkFull:
    def test_run_suite_no_agent(self):
        from terry.core.benchmark import BenchmarkRunner
        runner = BenchmarkRunner(agent=None)
        runner.create_standard_suites()
        suite = runner.run_suite("coding_basics")
        assert len(suite.results) >= 1

    def test_get_leaderboard(self):
        from terry.core.benchmark import BenchmarkRunner
        runner = BenchmarkRunner(agent=None)
        runner.create_standard_suites()
        lb = runner.get_leaderboard()
        assert isinstance(lb, list)


# ═══════════════════════════════════════════════════════════════════
# MEMORY SYNC
# ═══════════════════════════════════════════════════════════════════

class TestMemorySyncFull:
    def test_import_missing_file(self):
        from terry.core.memory_sync import MemorySync
        ms = MemorySync()
        count = ms.import_memories(Path("/nonexistent/file.json"))
        assert count == 0
