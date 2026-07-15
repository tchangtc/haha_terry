"""Tests for the Textual TUI (terry/tui/app.py).

Widget ``render()`` methods are checked directly; the full app (compose,
on_mount, input handling, scroll actions) is driven through Textual's
``run_test()`` pilot so no real terminal is needed.
"""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Input

from terry.tui.app import ChatMessage, StatusLine, TaskPanel, TerryTUI


class FakeTuiAgent:
    def __init__(self, response="agent reply", raises=False):
        self._response = response
        self._raises = raises

    def run(self, text):
        if self._raises:
            raise RuntimeError("kaboom")
        return self._response


class TestWidgetRender:
    def test_chat_message_user(self):
        out = ChatMessage("user", "hello", timestamp="09:30").render()
        assert "👤" in out and "hello" in out and "09:30" in out

    def test_chat_message_assistant(self):
        out = ChatMessage("assistant", "hi back").render()
        assert "🤖" in out and "hi back" in out

    def test_task_panel_empty(self):
        assert "No active plan" in TaskPanel().render()

    def test_task_panel_with_tasks(self):
        panel = TaskPanel()
        panel.tasks = [
            {"status": "completed", "description": "read code"},
            {"status": "in_progress", "description": "refactor"},
            {"status": "pending", "description": "test"},
        ]
        out = panel.render()
        assert "✅" in out and "🔄" in out and "⬜" in out
        assert "read code" in out

    def test_status_line_idle(self):
        assert "Ready" in StatusLine().render()

    def test_status_line_with_metrics(self):
        line = StatusLine()
        line.tokens = 2300
        line.cost = 0.1234
        line.progress = "thinking"
        out = line.render()
        assert "2,300" in out and "$0.1234" in out and "thinking" in out


class TestTerryTUIConstruction:
    def test_init_stores_agent(self):
        agent = FakeTuiAgent()
        app = TerryTUI(agent=agent)
        assert app.agent is agent
        assert app._messages == []

    def test_bindings_present(self):
        keys = {b[0] if isinstance(b, tuple) else b.key for b in TerryTUI.BINDINGS}
        assert "ctrl+q" in keys and "ctrl+o" in keys and "j" in keys


class TestTerryTUIPilot:
    async def test_mounts_and_focuses_input(self):
        app = TerryTUI(agent=FakeTuiAgent())
        async with app.run_test() as pilot:
            inp = app.query_one("#user-input", Input)
            assert inp.has_focus
            await pilot.pause()

    async def test_input_submitted_runs_agent(self):
        app = TerryTUI(agent=FakeTuiAgent("here you go"))
        async with app.run_test() as pilot:
            app.query_one("#user-input", Input).value = "do a thing"
            await pilot.press("enter")
            await pilot.pause()
            msgs = list(app.query(ChatMessage))
            assert len(msgs) == 2  # user echo + assistant reply
            rendered = " ".join(m.render() for m in msgs)
            assert "do a thing" in rendered and "here you go" in rendered

    async def test_empty_input_is_ignored(self):
        app = TerryTUI(agent=FakeTuiAgent())
        async with app.run_test() as pilot:
            app.query_one("#user-input", Input).value = "   "
            await pilot.press("enter")
            await pilot.pause()
            assert list(app.query(ChatMessage)) == []

    async def test_agent_error_is_shown(self):
        app = TerryTUI(agent=FakeTuiAgent(raises=True))
        async with app.run_test() as pilot:
            app.query_one("#user-input", Input).value = "boom"
            await pilot.press("enter")
            await pilot.pause()
            rendered = " ".join(m.render() for m in app.query(ChatMessage))
            assert "Error" in rendered

    async def test_no_agent_shows_hint(self):
        app = TerryTUI(agent=None)
        async with app.run_test() as pilot:
            app.query_one("#user-input", Input).value = "hi"
            await pilot.press("enter")
            await pilot.pause()
            rendered = " ".join(m.render() for m in app.query(ChatMessage))
            assert "not connected" in rendered

    async def test_scroll_actions_do_not_error(self):
        app = TerryTUI(agent=FakeTuiAgent())
        async with app.run_test() as pilot:
            app.action_scroll_down()
            app.action_scroll_up()
            app.action_scroll_home()
            app.action_scroll_end()
            app.action_toggle_focus()
            await pilot.pause()

    async def test_toggle_focus_cycles_chat_and_input(self):
        app = TerryTUI(agent=FakeTuiAgent())
        async with app.run_test() as pilot:
            chat = app.query_one("#chat", VerticalScroll)
            user_input = app.query_one("#user-input", Input)
            assert user_input.has_focus  # input is focused on mount
            app.action_toggle_focus()  # input → chat
            await pilot.pause()
            assert chat.has_focus
            app.action_toggle_focus()  # chat → input
            await pilot.pause()
            assert user_input.has_focus and not chat.has_focus


def test_run_tui_constructs_and_runs(monkeypatch):
    import terry.tui.app as tui

    started = {}
    monkeypatch.setattr(TerryTUI, "run", lambda self: started.setdefault("agent", self.agent))
    agent = FakeTuiAgent()
    tui.run_tui(agent=agent)
    assert started["agent"] is agent
