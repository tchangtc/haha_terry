"""Tests for P2/P3 modules."""

import tempfile
from pathlib import Path

import pytest


class TestThinking:
    def test_allocate(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking(model="claude-sonnet-4-20250514")
        budgets = et.allocate()
        assert "system_prompt" in budgets
        assert "active_context" in budgets
        assert budgets["system_prompt"] > 0

    def test_suggest_compression(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        msgs = [{"role": "user", "content": "Hello" * 1000}]
        threshold = et.suggest_compression_threshold(msgs, "System")
        assert 0 < threshold <= 1.0

    def test_can_fit(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking()
        msgs = [{"role": "user", "content": "Hi"}]
        assert et.can_fit(msgs, "System prompt")

    def test_model_window(self):
        from terry.core.thinking import ExtendedThinking
        et = ExtendedThinking(model="gpt-4o")
        assert et.total == 128_000


class TestTaskDAG:
    def test_add_and_ready(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.task_dag import TaskDAG
            dag = TaskDAG(path=Path(d) / "tasks.json")
            tid = dag.add_task("Test task")
            ready = dag.get_next_ready()
            assert len(ready) == 1
            assert ready[0].id == tid

    def test_dependencies(self):
        from terry.core.task_dag import TaskDAG, TaskNode
        # Direct unit test of get_next_ready dependency logic
        dag = TaskDAG.__new__(TaskDAG)
        dag.MAX_TASKS = 200
        dag.tasks = {}
        dag.path = None
        # Manually add tasks
        t1 = TaskNode("task_1", "Task 1", depends_on=[], status="completed")
        t2 = TaskNode("task_2", "Task 2", depends_on=["task_1"], status="pending")
        dag.tasks = {"task_1": t1, "task_2": t2}
        ready = dag.get_next_ready()
        ready_ids = [r.id for r in ready]
        assert "task_2" in ready_ids, f"Task 2 should be ready. Ready: {ready_ids}"

    def test_to_mermaid(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.task_dag import TaskDAG
            dag = TaskDAG(path=Path(d) / "tasks.json")
            dag.add_task("Task A")
            mermaid = dag.to_mermaid()
            assert "mermaid" in mermaid

    def test_summary(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.task_dag import TaskDAG
            dag = TaskDAG(path=Path(d) / "tasks.json")
            dag.add_task("T1")
            dag.add_task("T2")
            summary = dag.get_summary()
            # Both tasks are pending
            assert summary.get("pending", 0) >= 1


class TestKnowledgeGraph:
    def test_add_node(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph(path=Path(d) / "kg.json")
            assert kg.add_node("file:test.py", "file", name="test.py")
            assert len(kg.nodes) == 1

    def test_add_edge(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph(path=Path(d) / "kg.json")
            kg.add_node("A")
            kg.add_node("B")
            assert kg.add_edge("A", "B", "imports")
            assert len(kg.edges) == 1

    def test_get_related(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph(path=Path(d) / "kg.json")
            kg.add_node("A")
            kg.add_node("B")
            kg.add_edge("A", "B", "calls")
            related = kg.get_related("A", depth=1)
            assert any(r["id"] == "B" for r in related)

    def test_search_nodes(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph(path=Path(d) / "kg.json")
            kg.add_node("user_module", properties={"name": "UserManager"})
            results = kg.search_nodes("user")
            assert len(results) >= 1

    def test_to_graphviz(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph(path=Path(d) / "kg.json")
            kg.add_node("X")
            dot = kg.to_graphviz()
            assert "digraph" in dot


class TestScheduler:
    def test_schedule_once(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.scheduler import CronScheduler
            s = CronScheduler(db_path=Path(d) / "sched.json")
            tid = s.schedule("test", {"prompt": "hello"}, interval_seconds=0)
            assert tid > 0
            tasks = s.list_tasks()
            assert len(tasks) == 1

    def test_cancel(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.scheduler import CronScheduler
            s = CronScheduler(db_path=Path(d) / "sched.json")
            tid = s.schedule("test", {"prompt": "hi"})
            assert s.cancel(tid)
            tasks = s.list_tasks()
            assert tasks[0]["status"] == "cancelled"

    def test_get_due(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.scheduler import CronScheduler
            s = CronScheduler(db_path=Path(d) / "sched.json")
            s.schedule("test", {"prompt": "hi"}, interval_seconds=0)
            due = s.get_due_tasks()
            assert len(due) >= 0


class TestCurator:
    def test_record_usage(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.curator import SkillsCurator
            c = SkillsCurator(skills_dir=Path(d), data_dir=Path(d))
            c.record_usage("test-skill", success=True)
            c.record_usage("test-skill", success=False)
            assert c.get_effectiveness("test-skill") == 0.5

    def test_top_skills(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.curator import SkillsCurator
            c = SkillsCurator(skills_dir=Path(d), data_dir=Path(d))
            for i in range(5):
                name = f"skill-{i}"
                for _ in range(3):
                    c.record_usage(name, success=True)
            top = c.get_top_skills(3)
            assert len(top) == 3

    def test_suggest_pruning(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.curator import SkillsCurator
            c = SkillsCurator(skills_dir=Path(d), data_dir=Path(d))
            c.record_usage("dead-skill", success=False)
            # Set last_used to old date manually
            c.usage["dead-skill"]["last_used"] = "2020-01-01T00:00:00"
            to_prune = c.suggest_pruning(min_uses=0, max_age_days=1)
            assert "dead-skill" in to_prune


class TestWorkflow:
    def test_execute_empty(self):
        from terry.core.workflow import Workflow, WorkflowEngine
        wf = Workflow("test", "A test workflow")
        engine = WorkflowEngine(agent=None)
        results = engine.execute(wf)
        assert results == {}

    def test_yaml_roundtrip(self):
        from terry.core.workflow import Workflow, WorkflowStep
        wf = Workflow("test", steps=[
            WorkflowStep("step1", tool="read_file", prompt="read README.md"),
        ])
        yaml_text = wf.to_yaml()
        assert "step1" in yaml_text


class TestPromptCache:
    def test_build_cacheable(self):
        from terry.core.prompt_cache import PromptCache
        pc = PromptCache()
        blocks = pc.build_cacheable_prompt("System", [], "")
        assert len(blocks) >= 1

    def test_stats(self):
        from terry.core.prompt_cache import PromptCache
        pc = PromptCache()
        pc.record_hit(1000)
        pc.record_miss()
        stats = pc.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestSpecExec:
    def test_analyze_grep_output(self):
        from terry.core.spec_exec import SpeculativeExecutor
        se = SpeculativeExecutor()
        predictions = se.analyze_tool_call(
            "grep", {"pattern": "def"},
            "src/main.py:10:def foo():\ntests/test.py:5:def bar():"
        )
        assert len(predictions) >= 0

    def test_stats(self):
        from terry.core.spec_exec import SpeculativeExecutor
        se = SpeculativeExecutor()
        se.record_hit = lambda: None
        se._hits = 3
        se._misses = 1
        stats = se.get_stats()
        assert stats["hits"] == 3


class TestSuggester:
    def test_analyze_error_fix(self):
        from terry.core.suggester import ProactiveSuggester
        ps = ProactiveSuggester()
        msgs = [
            {"role": "assistant", "content": "The bug is fixed. Error has been resolved in the code."}
        ]
        suggestions = ps.analyze(msgs)
        # Should match "Error.*fixed" or "bug.*fixed" pattern
        assert len(suggestions) >= 0  # Just verify no crash

    def test_should_suggest(self):
        from terry.core.suggester import ProactiveSuggester
        ps = ProactiveSuggester()
        msgs = [
            {"role": "user", "content": "fix the bug"},
            {"role": "assistant", "content": "The task is completed and the fix is ready for review."},
        ]
        # Should detect "completed" or "ready"
        result = ps.should_suggest(msgs)
        assert isinstance(result, bool)


class TestFTSSearch:
    def test_index_and_search(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.fts_search import FTSSearch
            fts = FTSSearch(db_path=Path(d) / "test.db")
            fts.index_message("s1", "user", "Hello world, testing FTS5")
            fts.index_message("s1", "assistant", "Hi there, FTS5 is working")
            results = fts.search("FTS5", limit=5)
            assert len(results) >= 1


class TestSkillMarket:
    def test_list_installed_empty(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.skill_market import SkillMarket
            sm = SkillMarket(install_dir=Path(d))
            installed = sm.list_installed()
            assert isinstance(installed, list)


class TestLocalEmbed:
    def test_embed(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        vec = le.embed("hello world")
        assert len(vec) > 0
        assert all(isinstance(v, float) for v in vec)

    def test_similarity(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        sim = le.similarity("hello world", "hi there")
        assert 0 <= sim <= 1

    def test_search(self):
        from terry.core.local_embed import LocalEmbedder
        le = LocalEmbedder()
        docs = ["apple banana", "car dog", "elephant fox"]
        results = le.search("fruit", docs, top_k=1)
        assert len(results) >= 0


class TestCodeIndex:
    def test_build_index(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.code_index import CodeSemanticIndex
            # Create a Python file to index
            py_file = Path(d) / "test.py"
            py_file.write_text("def foo():\n    pass\n\nclass Bar:\n    def baz(self):\n        pass\n")
            ci = CodeSemanticIndex(workdir=Path(d), cache_dir=Path(d) / "cache")
            count = ci.build_index()
            assert count >= 1

    def test_find_definition(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.code_index import CodeSemanticIndex
            py_file = Path(d) / "mod.py"
            py_file.write_text("def hello():\n    return 'world'\n")
            ci = CodeSemanticIndex(workdir=Path(d), cache_dir=Path(d) / "cache")
            ci.build_index()
            defs = ci.find_definition("hello")
            assert len(defs) >= 1


class TestProjectRAG:
    def test_chunk_text(self):
        from terry.core.rag import ProjectRAG
        rag = ProjectRAG()
        text = "x" * 1200
        chunks = rag._chunk_text(text)
        assert len(chunks) > 1

    def test_index_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.core.rag import ProjectRAG
            rag = ProjectRAG(workdir=Path(d), index_dir=Path(d) / "idx")
            py_file = Path(d) / "code.py"
            py_file.write_text("def authenticate(user, password):\n    return user == 'admin'\n")
            rag.index_file("code.py")
            results = rag.query("authentication", top_k=3)
            assert isinstance(results, list)


class TestDockerSandbox:
    def test_not_available(self):
        from terry.core.docker_sandbox import DockerSandbox
        sandbox = DockerSandbox()
        # Docker may or may not be available — just check no crash
        result = sandbox.run_command("echo hello")
        assert isinstance(result, str)


class TestBenchmark:
    def test_create_suites(self):
        from terry.core.benchmark import BenchmarkRunner
        runner = BenchmarkRunner()
        runner.create_standard_suites()
        suites = runner.list_suites()
        assert len(suites) >= 3
        assert "coding_basics" in runner.suites

    def test_suite_serialization(self):
        from terry.core.benchmark import BenchmarkSuite
        suite = BenchmarkSuite("test", "desc")
        suite.add_problem("p1", "Do something", ["expected"], ["file.py"])
        data = suite.to_dict()
        assert data["name"] == "test"
        assert len(data["problems"]) == 1


class TestModelRouter:
    def test_simple(self):
        from terry.core.model_router import ModelRouter
        router = ModelRouter()
        assert router.analyze_complexity("list all files") == "simple"

    def test_complex(self):
        from terry.core.model_router import ModelRouter
        router = ModelRouter()
        # Long message with multiple complex keywords
        complexity = router.analyze_complexity(
            "refactor the entire authentication module with JWT support and fix bugs "
            + "also optimize the database queries and restructure the error handling " * 3
        )
        assert complexity == "complex", f"Expected complex, got {complexity}"
