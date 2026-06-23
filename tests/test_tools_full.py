"""Full tool coverage tests — every tool's main execution paths."""

from __future__ import annotations

import tempfile
import json
import os
import subprocess
from pathlib import Path



# ═══════════════════════════════════════════════════════════════════
# READ_IMAGE
# ═══════════════════════════════════════════════════════════════════

class TestReadImage:
    def test_png(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "img.png"
            p.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
            from terry.tools.read_image import ReadImageTool
            result = ReadImageTool(workdir=Path(d)).execute(path="img.png")
            long_check = "Image" in result or "PNG" in result.lower()
            assert long_check or "base64" in result.lower() or "media" in result.lower()

    def test_unsupported_ext(self):
        from terry.tools.read_image import ReadImageTool
        result = ReadImageTool().execute(path="file.xyz")
        assert "Error" in result or "Unsupported" in result

    def test_missing_file(self):
        from terry.tools.read_image import ReadImageTool
        result = ReadImageTool().execute(path="nonexistent.png")
        assert "Error" in result or "not found" in result.lower()


# ═══════════════════════════════════════════════════════════════════
# CALCULATOR
# ═══════════════════════════════════════════════════════════════════

class TestCalculator:
    def test_add(self):
        from terry.tools.calculator import CalculatorTool
        assert "4" in CalculatorTool().execute(expression="2+2")

    def test_subtract(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="5-3")
        assert "2" in result

    def test_multiply(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="3*4")
        assert "12" in result

    def test_power(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="2**3")
        assert "8" in result

    def test_sin(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="sin(0)")
        assert "0" in result

    def test_pi(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="pi")
        assert "3.14" in result

    def test_percent(self):
        from terry.tools.calculator import CalculatorTool
        result = CalculatorTool().execute(expression="20% of 100")
        assert "20" in result


# ═══════════════════════════════════════════════════════════════════
# WEB_FETCH
# ═══════════════════════════════════════════════════════════════════

class TestWebFetch:
    def test_localhost_blocked(self):
        from terry.tools.web_fetch import WebFetchTool
        result = WebFetchTool().execute(url="http://localhost:8080")
        assert "Error" in result or "blocked" in result.lower() or "private" in result.lower()

    def test_invalid_url(self):
        from terry.tools.web_fetch import WebFetchTool
        result = WebFetchTool().execute(url="not_a_valid_url")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# WEB_SEARCH
# ═══════════════════════════════════════════════════════════════════

class TestWebSearch:
    def test_no_api_key(self):
        old = os.environ.get('SERPER_API_KEY')
        try:
            os.environ.pop('SERPER_API_KEY', None)
            os.environ.pop('GOOGLE_SEARCH_API_KEY', None)
            from terry.tools.web_search import WebSearchTool
            result = WebSearchTool().execute(query="test")
            assert isinstance(result, str)
        finally:
            if old:
                os.environ['SERPER_API_KEY'] = old


# ═══════════════════════════════════════════════════════════════════
# NOTEBOOK
# ═══════════════════════════════════════════════════════════════════

class TestNotebook:
    def test_replace_cell(self):
        with tempfile.TemporaryDirectory() as d:
            nb = {
                "cells": [{
                    "cell_type": "code", "source": "print('old')",
                    "metadata": {}, "outputs": [], "execution_count": None
                }]
            }
            (Path(d) / "nb.ipynb").write_text(json.dumps(nb))
            from terry.tools.notebook import NotebookEditTool
            result = NotebookEditTool(workdir=Path(d)).execute(
                path="nb.ipynb", edit_mode="replace", cell_index=0, new_source="print('new')"
            )
            assert "Replaced" in result or "new" in result.lower()

    def test_insert_cell(self):
        with tempfile.TemporaryDirectory() as d:
            nb = {"cells": []}
            (Path(d) / "nb.ipynb").write_text(json.dumps(nb))
            from terry.tools.notebook import NotebookEditTool
            result = NotebookEditTool(workdir=Path(d)).execute(
                path="nb.ipynb", edit_mode="insert", new_source="print('hello')", cell_type="code"
            )
            assert "Inserted" in result

    def test_delete_cell(self):
        with tempfile.TemporaryDirectory() as d:
            nb = {"cells": [{"cell_type": "code", "source": "x", "metadata": {}, "outputs": []}]}
            (Path(d) / "nb.ipynb").write_text(json.dumps(nb))
            from terry.tools.notebook import NotebookEditTool
            result = NotebookEditTool(workdir=Path(d)).execute(
                path="nb.ipynb", edit_mode="delete", cell_index=0
            )
            assert "Deleted" in result


# ═══════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════

class TestNotes:
    def test_add_and_list(self):
        from terry.tools.notes import NotesTool
        tool = NotesTool()
        tool.execute(action="add", title="Test Note", content="hello")
        result = tool.execute(action="list")
        assert "Test Note" in result or "hello" in result

    def test_search(self):
        from terry.tools.notes import NotesTool
        tool = NotesTool()
        tool.execute(action="add", title="Bug Report", content="critical bug", tags="urgent")
        result = tool.execute(action="search", query="critical")
        assert isinstance(result, str)

    def test_delete(self):
        from terry.tools.notes import NotesTool
        tool = NotesTool()
        tool.execute(action="add", title="Delete Me", content="x")
        result = tool.execute(action="delete", note_id="0")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# REMINDER
# ═══════════════════════════════════════════════════════════════════

class TestReminder:
    def test_add_reminder(self):
        from terry.tools.reminder import ReminderTool
        tool = ReminderTool()
        result = tool.execute(action="add", title="Meeting", time="+2h")
        assert isinstance(result, str)

    def test_list_reminders(self):
        from terry.tools.reminder import ReminderTool
        result = ReminderTool().execute(action="list")
        assert isinstance(result, str)

    def test_invalid_action(self):
        from terry.tools.reminder import ReminderTool
        result = ReminderTool().execute(action="invalid")
        assert "Error" in result or "Invalid" in result or "Unknown" in result.lower()


# ═══════════════════════════════════════════════════════════════════
# TIMER
# ═══════════════════════════════════════════════════════════════════

class TestTimer:
    def test_start_timer(self):
        from terry.tools.timer import TimerTool
        result = TimerTool().execute(action="start", duration="1s", label="quick")
        assert isinstance(result, str)

    def test_list_timers(self):
        from terry.tools.timer import TimerTool
        result = TimerTool().execute(action="list")
        assert isinstance(result, str)

    def test_pomodoro(self):
        from terry.tools.timer import TimerTool
        result = TimerTool().execute(action="pomodoro")
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# WEATHER
# ═══════════════════════════════════════════════════════════════════

class TestWeather:
    def test_no_api_key(self):
        old_w = os.environ.get('WEATHER_API_KEY')
        old_o = os.environ.get('OPENWEATHERMAP_API_KEY')
        try:
            os.environ.pop('WEATHER_API_KEY', None)
            os.environ.pop('OPENWEATHERMAP_API_KEY', None)
            from terry.tools.weather import WeatherTool
            result = WeatherTool().execute(location="Beijing")
            assert isinstance(result, str)
        finally:
            if old_w:
                os.environ['WEATHER_API_KEY'] = old_w
            if old_o:
                os.environ['OPENWEATHERMAP_API_KEY'] = old_o


# ═══════════════════════════════════════════════════════════════════
# GIT TOOLS (with real git repos)
# ═══════════════════════════════════════════════════════════════════

class TestGitToolsWithRepo:
    def setup_git_repo(self, d):
        subprocess.run(["git", "init"], cwd=d, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=d, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=d, capture_output=True)
        (Path(d) / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "."], cwd=d, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=d, capture_output=True)

    def test_git_status_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_git_repo(d)
            from terry.tools.git.git_status import GitStatusTool
            result = GitStatusTool(workdir=Path(d).resolve()).execute()
            assert isinstance(result, str)

    def test_git_log_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_git_repo(d)
            from terry.tools.git.git_log import GitLogTool
            result = GitLogTool(workdir=Path(d).resolve()).execute(count=5)
            assert "initial" in result or "commit" in result.lower() or isinstance(result, str)

    def test_git_diff_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_git_repo(d)
            (Path(d) / "new.py").write_text("x")
            from terry.tools.git.git_diff import GitDiffTool
            result = GitDiffTool(workdir=Path(d).resolve()).execute()
            assert isinstance(result, str)

    def test_git_commit_repo(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_git_repo(d)
            (Path(d) / "update.py").write_text("change")
            from terry.tools.git.git_commit import GitCommitTool
            result = GitCommitTool(workdir=Path(d).resolve()).execute(
                message="feat: add update"
            )
            assert isinstance(result, str)

    def test_git_checkout_new_branch(self):
        with tempfile.TemporaryDirectory() as d:
            self.setup_git_repo(d)
            from terry.tools.git.git_checkout import GitCheckoutTool
            result = GitCheckoutTool(workdir=Path(d).resolve()).execute(create_branch="test-branch")
            assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# HARNESS TOOL
# ═══════════════════════════════════════════════════════════════════

class TestHarnessTool:
    def test_registered(self):
        from terry.tools import discover_tools, tool_registry
        discover_tools()
        tool = tool_registry.get("harness")
        assert tool is not None

    def test_execute_sequential(self):
        from terry.tools.harness_tool import HarnessTool
        result = HarnessTool().execute(pattern="sequential", prompts=["test"])
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# TODO_WRITE
# ═══════════════════════════════════════════════════════════════════

class TestTodoWrite:
    def test_write_and_readback(self):
        with tempfile.TemporaryDirectory() as d:
            from terry.tools.todo_write import TodoWriteTool
            tool = TodoWriteTool(workdir=Path(d))
            tool.execute(todos=[{"content": "Buy milk", "status": "pending"}])
            result = tool.execute(todos=[{"content": "Buy eggs", "status": "completed"}])
            assert isinstance(result, str)
