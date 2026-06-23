"""Coverage tests for previously uncovered v0.7-v0.9 modules."""
import pytest
import os
from pathlib import Path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestTaskManager:
    def test_create_plan(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tasks = tm.create_plan("test goal", ["step 1", "step 2", "step 3"])
        assert len(tasks) == 3
        assert tm.is_active()
        assert tm.get_summary()["pending"] == 3

    def test_mark_and_progress(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tasks = tm.create_plan("test", ["a", "b"])
        tm.mark(tasks[0].id, "completed")
        assert tm.get_summary()["completed"] == 1
        assert tm.progress_str() == "[1/2] ✅⬜"

    def test_get_next_ready(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tm.create_plan("test", ["a", "b"])
        t = tm.get_next_ready()
        assert t is not None
        assert t.description == "a"

    def test_save_and_load(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tm.create_plan("save test", ["x", "y"])
        tm.mark(tm.get_next_ready().id, "completed")
        tm2 = TaskManager()
        assert tm2.load()
        assert tm2.get_summary()["completed"] == 1

    def test_clear(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tm.create_plan("test", ["a"])
        tm.clear()
        assert not tm.is_active()

    def test_mark_invalid_status(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tasks = tm.create_plan("test", ["a"])
        assert not tm.mark(tasks[0].id, "invalid_status")
        assert not tm.mark("nonexistent", "completed")

    def test_tool_format(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tm.create_plan("build feature", ["read code", "write code", "test"])
        fmt = tm.to_tool_format()
        assert "build feature" in fmt
        assert "⬜" in fmt

    def test_empty_progress(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        assert tm.progress_str() == ""

    def test_guess_tool(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tools = ["read_file", "write_file", "edit_file", "bash", "grep"]
        assert tm._guess_tool("read the code", tools) == "read_file"
        assert tm._guess_tool("write a test", tools) == "write_file"
        assert tm._guess_tool("edit the config", tools) == "edit_file"
        assert tm._guess_tool("search for bugs", tools) == "grep"
        assert tm._guess_tool("run the tests", tools) == "bash"

    def test_to_list(self):
        from terry.core.task_manager import TaskManager
        tm = TaskManager()
        tm.create_plan("t", ["a", "b"])
        lst = tm.to_list()
        assert len(lst) == 2
        assert lst[0]["status"] == "pending"


class TestTeleport:
    def test_export_empty_session(self):
        from terry.core.config import TerryConfig
        from terry.core.agent import Agent
        from terry.core.teleport import TeleportExporter
        cfg = TerryConfig()

        cfg.model.api_key = "test"
        agent = Agent(cfg, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        exporter = TeleportExporter()
        path = exporter.export(agent, "test-export")
        assert path.exists()
        assert path.suffix == '.gz'
        path.unlink()

    def test_import_archive(self):
        from terry.core.config import TerryConfig
        from terry.core.agent import Agent
        from terry.core.teleport import TeleportExporter, TeleportImporter
        cfg = TerryConfig()

        cfg.model.api_key = "test"
        agent = Agent(cfg, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        # Add a message before export
        agent.messages = [{"role": "user", "content": "hello"}]
        path = TeleportExporter().export(agent, "import-test")
        result = TeleportImporter().import_archive(agent, path)
        assert result["restored"]
        assert result["messages"] > 0
        path.unlink()

    def test_import_nonexistent(self):
        from terry.core.config import TerryConfig
        from terry.core.agent import Agent
        from terry.core.teleport import TeleportImporter
        cfg = TerryConfig()

        cfg.model.api_key = "test"
        agent = Agent(cfg, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)
        result = TeleportImporter().import_archive(agent, Path("/nonexistent.tar.gz"))
        assert not result["restored"]


class TestSkillRegistry:
    def test_init(self):
        from terry.core.skill_registry import SkillRegistry
        sr = SkillRegistry()
        assert sr.registry_url is not None

    def test_search_empty(self):
        from terry.core.skill_registry import SkillRegistry
        sr = SkillRegistry()
        sr._index = {"skills": []}
        sr._loaded = True
        results = sr.search("nonexistent")
        assert results == []

    def test_list_remote_empty(self):
        from terry.core.skill_registry import SkillRegistry
        sr = SkillRegistry()
        sr._index = {"skills": []}
        sr._loaded = True
        results = sr.list_remote()
        assert results == []

    def test_search_with_data(self):
        from terry.core.skill_registry import SkillRegistry
        sr = SkillRegistry()
        sr._index = {"skills": [
            {"name": "terry-code-review", "description": "Code review skill", "repo": "https://github.com/x/y"}
        ]}
        sr._loaded = True
        results = sr.search("code review")
        assert len(results) == 1
        assert results[0].name == "terry-code-review"

    def test_install_no_repo(self):
        from terry.core.skill_registry import SkillRegistry
        sr = SkillRegistry()
        sr._index = {"skills": [{"name": "test-skill", "repo": ""}]}
        sr._loaded = True
        assert not sr.install("test-skill")


class TestWorkflowScript:
    def test_fan_out(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").fan_out(["a", "b", "c"]).synthesize()
        assert wf._pattern is not None
        assert len(wf._stages) == 5  # 3 tasks + merge + synthesize

    def test_tournament(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").tournament(["approach a", "approach b"])
        assert len(wf._stages) == 3  # 2 contestants + judge

    def test_verify(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").fan_out(["a"]).verify(adversarial=5)
        assert wf._verifiers == 5

    def test_classify_execute(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").classify_execute("task", ["h1", "h2"])
        assert len(wf._stages) == 3  # classify + 2 handlers

    def test_loop_until_done(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").loop_until_done("task", max_iterations=7)
        assert wf._max_iterations == 7

    def test_generate_filter(self):
        from terry.core.workflow_script import WorkflowScript
        wf = WorkflowScript("test").generate_filter("topic", count=15)
        assert len(wf._stages) == 2

    def test_no_pattern_raises(self):
        from terry.core.workflow_script import WorkflowScript, WorkflowScriptError
        wf = WorkflowScript("test")
        with pytest.raises(WorkflowScriptError):
            wf.run(agent_factory=None)


class TestUltrareview:
    def test_init(self):
        from terry.core.ultrareview import Ultrareview
        ur = Ultrareview()
        assert ur.max_iterations == 3

    def test_review_no_agent(self):
        from terry.core.ultrareview import Ultrareview
        ur = Ultrareview(agent_factory=None)
        result = ur.review("def foo(): pass")
        assert result.passed

    def test_parse_findings_json(self):
        from terry.core.ultrareview import Ultrareview
        ur = Ultrareview()
        findings = ur._parse_findings(
            "correctness",
            '[{"severity":"major","location":"L1","description":"bug","suggestion":"fix"}]'
        )
        assert len(findings) == 1
        assert findings[0].severity == "major"

    def test_parse_findings_empty(self):
        from terry.core.ultrareview import Ultrareview
        ur = Ultrareview()
        findings = ur._parse_findings("security", "not json at all\njust some text")
        assert findings == []


class TestSlashCommand:
    def test_register(self):
        from terry.tools.slash_command import SlashCommandTool
        tool = SlashCommandTool()
        assert tool.name == "slash_command"

    def test_block_exit(self):
        from terry.tools.slash_command import SlashCommandTool
        tool = SlashCommandTool()
        result = tool.execute("/exit")
        assert "Error" in result or "not available" in result.lower()

    def test_unknown_command(self):
        from terry.tools.slash_command import SlashCommandTool
        tool = SlashCommandTool()
        result = tool.execute("/nonexistent_xyz")
        assert "Error" in result


class TestDesignSystem:
    def test_theme_colors(self):
        from terry.core.theme import TerryTheme
        assert TerryTheme.PRIMARY == "#7c3aed"
        assert TerryTheme.BG == "#0f0f1a"
        assert "completed" in TerryTheme.STATUS_COLORS

    def test_theme_presets(self):
        from terry.core.theme import TerryTheme
        table = TerryTheme.table_style()
        assert "border_style" in table
        panel = TerryTheme.panel_default()
        assert "border_style" in panel

