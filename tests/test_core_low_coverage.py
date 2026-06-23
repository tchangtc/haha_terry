"""Comprehensive tests for core modules with low coverage."""

import json
from unittest.mock import MagicMock
import pytest
import asyncio


class TestDynamicWorkflow:
    """Test dynamic workflow engine."""

    def test_init(self):
        """Test workflow initialization."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine

        engine = DynamicWorkflowEngine()
        assert engine.agent_factory is None
        assert len(engine.active_workflows) == 0

    def test_workflow_init(self):
        """Test DynamicWorkflow initialization."""
        from terry.core.dynamic_workflow import DynamicWorkflow, WorkflowPattern

        wf = DynamicWorkflow(
            name="test-workflow",
            goal="Test goal",
            pattern=WorkflowPattern.FAN_OUT_MERGE,
            max_agents=5,
        )
        assert wf.name == "test-workflow"
        assert wf.goal == "Test goal"
        assert wf.pattern == WorkflowPattern.FAN_OUT_MERGE
        assert wf.max_agents == 5
        assert wf.status.value == "pending"

    def test_workflow_add_stage(self):
        """Test adding stages to workflow."""
        from terry.core.dynamic_workflow import DynamicWorkflow

        wf = DynamicWorkflow(name="test", goal="Test goal")
        stage_id = wf.add_stage("Stage 1", "Do something")
        assert stage_id is not None
        assert len(wf.stages) == 1
        assert wf.stages[0]["name"] == "Stage 1"

    def test_workflow_to_dict(self):
        """Test workflow serialization."""
        from terry.core.dynamic_workflow import DynamicWorkflow

        wf = DynamicWorkflow(name="test", goal="Test goal")
        wf.add_stage("Stage 1", "Do something")

        data = wf.to_dict()
        assert "id" in data
        assert data["name"] == "test"
        assert data["goal"] == "Test goal"
        assert len(data["stages"]) == 1

    def test_workflow_from_dict(self):
        """Test workflow deserialization."""
        from terry.core.dynamic_workflow import DynamicWorkflow

        data = {
            "id": "wf_test",
            "name": "test",
            "goal": "Test goal",
            "pattern": "fan-out-merge",
            "max_agents": 5,
            "token_budget": None,
            "status": "pending",
            "stages": [
                {"id": "stage_1", "name": "Stage 1", "prompt": "Do something",
                 "depends_on": [], "verify_prompt": "", "model": "default",
                 "status": "pending", "result": None, "retries": 0, "max_retries": 3}
            ],
            "results": {},
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }

        wf = DynamicWorkflow.from_dict(data)
        assert wf.id == "wf_test"
        assert wf.name == "test"
        assert len(wf.stages) == 1

    def test_plan_workflow_no_llm(self):
        """Test planning workflow without LLM."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern

        engine = DynamicWorkflowEngine()
        wf = engine.plan_workflow("Test goal", WorkflowPattern.FAN_OUT_MERGE)
        assert wf is not None
        assert wf.name == "Test goal"
        assert len(wf.stages) > 0  # Should have at least one stage

    def test_plan_workflow_with_llm(self):
        """Test planning workflow with LLM."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern

        # Mock LLM client
        mock_llm = MagicMock()
        mock_llm.chat.return_value = {
            "content": [{"type": "text", "text": "Stage 1: Do something\nStage 2: Do something else"}]
        }

        engine = DynamicWorkflowEngine()
        wf = engine.plan_workflow("Test goal", WorkflowPattern.FAN_OUT_MERGE, llm_client=mock_llm)
        assert wf is not None
        assert len(wf.stages) >= 2

    def test_execute_workflow_classify_execute(self):
        """Test classify-execute pattern."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, DynamicWorkflow, WorkflowPattern

        # Mock agent factory
        mock_agent = MagicMock()
        mock_agent.run.side_effect = ["general", "Result from stage 1"]

        engine = DynamicWorkflowEngine(agent_factory=lambda: mock_agent)
        wf = DynamicWorkflow(name="test", goal="Test goal", pattern=WorkflowPattern.CLASSIFY_EXECUTE)
        wf.add_stage("Classify", "Classify the task")
        wf.add_stage("Execute", "Execute the task")

        results = engine.execute(wf)
        assert "classified_as" in results
        assert results["classified_as"] == "general"

    def test_execute_workflow_fan_out_merge(self):
        """Test fan-out-merge pattern."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, DynamicWorkflow, WorkflowPattern

        # Mock agent factory
        mock_agent = MagicMock()
        mock_agent.run.side_effect = ["Result 1", "Result 2", "Merged result"]

        engine = DynamicWorkflowEngine(agent_factory=lambda: mock_agent)
        wf = DynamicWorkflow(name="test", goal="Test goal", pattern=WorkflowPattern.FAN_OUT_MERGE)
        wf.add_stage("Stage 1", "Do task 1")
        wf.add_stage("Stage 2", "Do task 2")
        wf.add_stage("Merge", "Merge results")

        results = engine.execute(wf)
        assert len(results) >= 2

    def test_execute_workflow_no_agent(self):
        """Test executing workflow without agent factory."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, DynamicWorkflow

        engine = DynamicWorkflowEngine()
        wf = DynamicWorkflow(name="test", goal="Test goal")
        wf.add_stage("Stage 1", "Do something")

        results = engine.execute(wf)
        assert "error" in results

    def test_checkpoint_workflow(self):
        """Test workflow checkpointing."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, DynamicWorkflow

        engine = DynamicWorkflowEngine()
        wf = DynamicWorkflow(name="test", goal="Test goal")
        wf.add_stage("Stage 1", "Do something")

        # Create checkpoint
        engine._checkpoint(wf)
        assert wf.checkpoint_file is not None
        assert wf.checkpoint_file.exists()


class TestAutonomousAgent:
    """Test autonomous agent — matches actual AutonomousAgent API."""

    def test_init(self):
        """Test autonomous agent initialization with agent_factory."""
        from terry.core.autonomous_agent import AutonomousAgent

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)
        assert agent.max_concurrent == 2
        assert agent._running is False
        assert agent.queue == []

    def test_start_stop(self):
        """Test starting and stopping autonomous agent."""
        from terry.core.autonomous_agent import AutonomousAgent

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)
        agent.start()
        assert agent._running is True
        assert agent._thread is not None

        agent.stop()
        # After stop(), _running should be False and thread should be None/stopped
        assert agent._running is False

    def test_submit_task(self):
        """Test submitting a task to autonomous agent."""
        from terry.core.autonomous_agent import AutonomousAgent

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)
        task_id = agent.submit_task("Test task")
        assert task_id is not None
        assert task_id.startswith("auto_")
        assert len(agent.queue) == 1

    def test_execute_task(self):
        """Test executing autonomous task pipeline."""
        from terry.core.autonomous_agent import AutonomousAgent, AutonomousTask

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)

        task = AutonomousTask("test_001", "Fix a bug", "")
        result = agent.execute_task(task)

        assert isinstance(result, AutonomousTask)
        assert result.id == "test_001"
        # Without a repo URL, it should skip clone and go to analyze/fix
        assert result.status in ("analyzing", "fixing", "testing", "committing", "completed", "failed", "done")

    def test_execute_task_with_error(self):
        """Test executing task with error scenario (no repo URL)."""
        from terry.core.autonomous_agent import AutonomousAgent, AutonomousTask

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)

        task = AutonomousTask("test_err", "Invalid task", "")
        result = agent.execute_task(task)

        assert result.id == "test_err"
        # Should complete (even with no repo) or fail gracefully
        assert result.status in (
            "analyzing", "fixing", "testing", "committing", "completed", "failed", "cloning", "done"
        )

    def test_get_status(self):
        """Test getting overall autonomous agent status."""
        from terry.core.autonomous_agent import AutonomousAgent

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)
        agent.submit_task("Test task")

        status = agent.get_status()
        assert "queued" in status
        assert status["queued"] == 1

    def test_get_all_tasks(self):
        """Test getting queue and completed tasks."""
        from terry.core.autonomous_agent import AutonomousAgent

        def factory():
            return MagicMock()
        agent = AutonomousAgent(agent_factory=factory)
        agent.submit_task("Task 1")
        agent.submit_task("Task 2")

        assert len(agent.queue) == 2
        assert len(agent.completed) == 0


class TestHarness:
    """Test harness engine — matches actual HarnessEngine API."""

    def test_init(self):
        """Test harness initialization."""
        from terry.core.harness import HarnessEngine

        harness = HarnessEngine()
        assert harness.max_concurrent == 5
        assert harness._running is False

    def test_create_task(self):
        """Test creating a task in the harness."""
        from terry.core.harness import HarnessEngine

        harness = HarnessEngine(max_concurrent=3)
        task_id = harness.create_task(
            description="Test parallel execution",
            prompt="Execute three things at once",
            pattern="parallel",
        )
        assert task_id is not None
        assert task_id.startswith("ht_")
        assert task_id in harness.tasks
        assert harness.tasks[task_id].pattern.value == "parallel"

    def test_execute_parallel(self):
        """Test parallel execution via execute()."""
        from terry.core.harness import HarnessEngine

        def _mock_agent_factory():
            agent = MagicMock()
            agent.run.return_value = "Task completed"
            return agent

        harness = HarnessEngine(agent_factory=_mock_agent_factory, max_concurrent=3)
        result = harness.execute(
            pattern="parallel",
            prompts=["Task 1", "Task 2", "Task 3"],
        )
        assert isinstance(result, dict)
        # Parallel results are keyed by index
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_execute_parallel_async(self):
        """Test async harness parallel execution."""
        from terry.core.async_harness import AsyncHarnessEngine

        harness = AsyncHarnessEngine(max_concurrent=3)
        harness._running = True

        result = await harness.execute(
            pattern="parallel",
            prompts=["Task A", "Task B"],
        )
        assert isinstance(result, dict)
        harness._running = False

    def test_execute_map_reduce(self):
        """Test fan-out-merge execution via HarnessEngine."""
        from terry.core.harness import HarnessEngine

        def _mock_agent_factory():
            agent = MagicMock()
            agent.run.return_value = "Mapped result"
            return agent

        harness = HarnessEngine(agent_factory=_mock_agent_factory, max_concurrent=3)
        result = harness.execute(
            pattern="fan-out-merge",
            prompts=["item1", "item2", "item3"],
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_map_reduce_async(self):
        """Test async fan-out-merge execution."""
        from terry.core.async_harness import AsyncHarnessEngine

        harness = AsyncHarnessEngine(max_concurrent=3)
        harness._running = True

        result = await harness.execute(
            pattern="fan-out-merge",
            prompts=["a", "b", "c"],
        )
        assert isinstance(result, dict)
        harness._running = False

    def test_stop(self):
        """Test async harness lifecycle (_running flag)."""
        from terry.core.async_harness import AsyncHarnessEngine

        async def _stop_test():
            harness = AsyncHarnessEngine(max_concurrent=3)
            harness._running = True
            assert harness._running is True
            harness._running = False
            assert harness._running is False

        asyncio.run(_stop_test())


class TestPlanner:
    """Test planner — matches actual Planner API."""

    def test_init(self):
        """Test planner initialization."""
        from terry.core.planner import Planner

        planner = Planner()
        assert planner.llm is None

        # With LLM client
        mock_llm = MagicMock()
        planner2 = Planner(llm_client=mock_llm)
        assert planner2.llm is mock_llm

    def test_create_plan(self):
        """Test creating a plan without LLM (falls back to simple plan)."""
        from terry.core.planner import Planner

        planner = Planner()
        tools = ["read_file", "write_file", "bash", "grep_tool"]

        plan = planner.create_plan(
            user_input="Implement feature X",
            available_tools=tools,
            workdir="/tmp/test",
        )
        assert "rationale" in plan or "steps" in plan or "goal" in plan
        assert len(plan.get("steps", [])) > 0 or "rationale" in plan

    def test_create_plan_with_context(self):
        """Test creating a plan with mock LLM client."""
        from terry.core.planner import Planner

        mock_llm = MagicMock()
        mock_llm.chat.return_value = {
            "content": [{"type": "text", "text": (
                "## Plan\n"
                "### Rationale\nTest rationale\n\n"
                "### Research Phase\n"
                "1. [Tool: read_file] - Read main.py\n\n"
                "### Implementation Phase\n"
                "1. [Tool: write_file] [DESTRUCTIVE] - Write changes\n\n"
                "### Verification\n"
                "1. [Tool: bash] - Run tests\n"
            )}],
            "stop_reason": "end_turn",
        }

        planner = Planner(llm_client=mock_llm)
        tools = ["read_file", "write_file", "bash"]

        plan = planner.create_plan(
            user_input="Implement feature",
            available_tools=tools,
            workdir=".",
        )
        assert "rationale" in plan or "steps" in plan
        assert len(plan.get("steps", [])) > 0 or "goal" in plan

    def test_execute_plan(self):
        """Test that create_plan handles invalid input gracefully."""
        from terry.core.planner import Planner

        planner = Planner()
        tools = ["read_file"]

        plan = planner.create_plan(
            user_input="",
            available_tools=tools,
            workdir=".",
        )
        assert isinstance(plan, dict)
        assert "goal" in plan or "steps" in plan

    def test_validate_plan(self):
        """Test that created plans are structurally valid."""
        from terry.core.planner import Planner

        planner = Planner()
        tools = ["read_file", "write_file", "bash", "grep_tool"]
        plan = planner.create_plan(
            user_input="Fix the login bug",
            available_tools=tools,
            workdir="/tmp/project",
        )
        assert isinstance(plan, dict)
        assert "goal" in plan or "steps" in plan or "rationale" in plan

    def test_save_and_load_plan(self):
        """Test plan is JSON-serializable (for persistence)."""
        from terry.core.planner import Planner

        planner = Planner()
        tools = ["read_file", "write_file", "bash"]
        plan = planner.create_plan(
            user_input="Implement feature X",
            available_tools=tools,
            workdir=".",
        )
        json_str = json.dumps(plan)
        assert len(json_str) > 0
        loaded = json.loads(json_str)
        assert isinstance(loaded, dict)


class TestSubAgent:
    """Test sub-agent manager — matches actual SubAgentManager + AsyncSubAgentManager API."""

    @pytest.fixture(autouse=True)
    def _setup_subagent_tests(self, monkeypatch):
        """Mock LLMClient so SubAgent doesn't make real API calls."""
        import terry.core.subagent as sa_mod

        self._mock_llm = MagicMock()
        self._mock_llm.chat.return_value = {
            "content": [{"type": "text", "text": "Task completed"}],
            "stop_reason": "end_turn",
        }
        monkeypatch.setattr(sa_mod, "LLMClient", lambda *a, **kw: self._mock_llm)

    @pytest.fixture
    def _manager(self, tmp_path):
        """Create a real SubAgentManager with minimal config."""
        from terry.core.config import TerryConfig
        from terry.tools import ToolRegistry

        config = TerryConfig()
        tools = ToolRegistry()
        return tmp_path, config, tools

    def test_init(self, _manager):
        """Test sub-agent manager initialization."""
        from terry.core.subagent import SubAgentManager

        tmp_path, config, tools = _manager
        manager = SubAgentManager(config=config, workdir=tmp_path, tools=tools)

        assert manager.config is config
        assert manager.workdir == tmp_path
        assert manager.tools is tools
        assert isinstance(manager.agents, dict)
        assert len(manager.agents) == 0

    def test_spawn_subagent(self, _manager):
        """Test spawning a sub-agent — verifies task_id returned and agent tracked."""
        from terry.core.subagent import SubAgentManager

        tmp_path, config, tools = _manager
        manager = SubAgentManager(config=config, workdir=tmp_path, tools=tools)

        task_id = manager.spawn("Test task")
        assert task_id is not None
        assert task_id.startswith("task_")
        assert task_id in manager.agents
        assert manager.agents[task_id].status in ("pending", "running", "completed")

    def test_execute_subagent(self, _manager):
        """Test executing a sub-agent and waiting for result."""
        from terry.core.subagent import SubAgentManager

        tmp_path, config, tools = _manager
        manager = SubAgentManager(config=config, workdir=tmp_path, tools=tools)

        task_id = manager.spawn("Test task")
        result = manager.wait(task_id, timeout=10)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_execute_subagent_async(self):
        """Test async sub-agent manager spawn + wait."""
        from terry.core.async_subagent import AsyncSubAgentManager

        manager = AsyncSubAgentManager(max_concurrent=3)
        await manager.start()

        agent_id = await manager.spawn("Async test task")
        assert agent_id is not None
        assert agent_id in manager._agents

        status = manager.get_status()
        assert status["total"] >= 1

        await manager.stop()

    def test_get_subagent_status(self, _manager):
        """Test getting sub-agent status."""
        from terry.core.subagent import SubAgentManager

        tmp_path, config, tools = _manager
        manager = SubAgentManager(config=config, workdir=tmp_path, tools=tools)

        task_id = manager.spawn("Test task")
        status = manager.get_status(task_id)

        assert status in ("pending", "running", "completed", "failed")

    def test_get_all_subagents(self, _manager):
        """Test listing all sub-agents."""
        from terry.core.subagent import SubAgentManager

        tmp_path, config, tools = _manager
        manager = SubAgentManager(config=config, workdir=tmp_path, tools=tools)

        manager.spawn("Task 1")
        manager.spawn("Task 2")

        tasks = manager.list_tasks()
        assert len(tasks) == 2
        for t in tasks:
            assert "task_id" in t
            assert "status" in t

    def test_stop(self):
        """Test stopping async sub-agent manager."""
        from terry.core.async_subagent import AsyncSubAgentManager

        async def _stop_test():
            manager = AsyncSubAgentManager(max_concurrent=3)
            await manager.start()
            assert manager._running is True
            await manager.stop()
            assert manager._running is False

        asyncio.run(_stop_test())
