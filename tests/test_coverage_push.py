"""Targeted tests for the biggest coverage gaps: cli_commands, desktop, agent_swarm."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════
# CLI COMMANDS — comprehensive handler testing
# ═══════════════════════════════════════════════════════════════════

class TestCLIHandlersDeep:
    def test_exit_returns_false(self):
        from terry.cli_commands import _cmd_exit
        assert _cmd_exit("/exit", None, MagicMock()) is False

    def test_new_calls_reset(self):
        from terry.cli_commands import _cmd_new
        agent = MagicMock()
        _cmd_new("/new", None, agent)
        agent.reset.assert_called_once()

    def test_save_with_name(self):
        from terry.cli_commands import _cmd_save
        agent = MagicMock()
        agent.save_session.return_value = "/tmp/s.json"
        _cmd_save("/save", "my-session", agent)
        agent.save_session.assert_called_once_with("my-session")

    def test_save_no_name(self):
        from terry.cli_commands import _cmd_save
        agent = MagicMock()
        agent.save_session.return_value = "/tmp/s.json"
        _cmd_save("/save", "", agent)
        assert agent.save_session.called

    def test_load_no_args(self):
        from terry.cli_commands import _cmd_load
        assert _cmd_load("/load", None, MagicMock()) is True

    def test_load_with_args(self):
        from terry.cli_commands import _cmd_load
        agent = MagicMock()
        _cmd_load("/load", "test", agent)
        agent.load_session.assert_called_once()

    def test_model_command(self):
        from terry.cli_commands import _cmd_model
        agent = MagicMock()
        agent.config.model.provider = "x"
        agent.config.model.model = "y"
        assert _cmd_model("/model", None, agent) is True

    def test_effort_no_args(self):
        from terry.cli_commands import _cmd_effort
        agent = MagicMock()
        agent.config.effort_level = "medium"
        assert _cmd_effort("/effort", None, agent) is True

    def test_effort_invalid(self):
        from terry.cli_commands import _cmd_effort
        assert _cmd_effort("/effort", "invalid", MagicMock()) is True

    def test_effort_valid(self):
        from terry.cli_commands import _cmd_effort
        agent = MagicMock()
        agent.set_effort.return_value = True
        _cmd_effort("/effort", "high", agent)
        agent.set_effort.assert_called_once_with("high")

    def test_mode_no_args(self):
        from terry.cli_commands import _cmd_mode
        agent = MagicMock()
        agent.cycle_mode.return_value = "auto"
        assert _cmd_mode("/mode", None, agent) is True

    def test_mode_with_args(self):
        from terry.cli_commands import _cmd_mode
        agent = MagicMock()
        agent.set_mode.return_value = True
        assert _cmd_mode("/mode", "ask", agent) is True

    def test_mode_invalid(self):
        from terry.cli_commands import _cmd_mode
        agent = MagicMock()
        agent.set_mode.return_value = False
        assert _cmd_mode("/mode", "bad", agent) is True

    def test_tools_command(self):
        from terry.cli_commands import _cmd_tools
        agent = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "t1"
        mock_tool.description = "d1"
        agent.tools.list_tools.return_value = [mock_tool]
        assert _cmd_tools("/tools", None, agent) is True

    def test_context_command(self):
        from terry.cli_commands import _cmd_context
        agent = MagicMock()
        agent.messages = [1, 2]
        agent.tool_call_count = 3
        agent.config.max_tool_calls = 100
        assert _cmd_context("/context", None, agent) is True

    def test_undo_no_checkpoint(self):
        from terry.cli_commands import _cmd_undo
        agent = MagicMock()
        agent.checkpoint_manager = None
        assert _cmd_undo("/undo", None, agent) is True

    def test_permissions_command(self):
        from terry.cli_commands import _cmd_permissions
        agent = MagicMock()
        agent.permission_store.list_rules.return_value = []
        agent.permission_level.value = "medium"
        assert _cmd_permissions("/permissions", None, agent) is True

    def test_btw_no_args(self):
        from terry.cli_commands import _cmd_btw
        assert _cmd_btw("/btw", None, MagicMock()) is True

    def test_btw_with_msg(self):
        from terry.cli_commands import _cmd_btw
        agent = MagicMock()
        agent.messages = []
        _cmd_btw("/btw", "note: fix port 3000", agent)
        assert len(agent.messages) == 1
        assert "port 3000" in agent.messages[0]["content"]

    def test_expand_empty(self):
        from terry.cli_commands import _cmd_expand
        agent = MagicMock()
        agent.messages = []
        assert _cmd_expand("/expand", None, agent) is True

    def test_expand_long(self):
        from terry.cli_commands import _cmd_expand
        agent = MagicMock()
        agent.messages = [{"role": "assistant", "content": "x" * 300}]
        assert _cmd_expand("/expand", None, agent) is True

    def test_editor_no_args(self):
        from terry.cli_commands import _cmd_editor_open
        assert _cmd_editor_open("/editor", None, MagicMock()) is True

    def test_editor_with_file(self):
        from terry.cli_commands import _cmd_editor_open
        agent = MagicMock()
        assert _cmd_editor_open("/editor", "main.py", agent) is True

    def test_cost_command(self):
        from terry.cli_commands import _cmd_cost
        agent = MagicMock()
        agent._cost_tracker = None
        assert _cmd_cost("/cost", None, agent) is True

    def test_hooks_command(self):
        from terry.cli_commands import _cmd_hooks_list
        assert _cmd_hooks_list("/hooks", None, MagicMock()) is True

    def test_discover_command(self):
        from terry.cli_commands import _cmd_discover
        assert _cmd_discover("/discover", None, MagicMock()) is True

    def test_vim_command(self):
        from terry.cli_commands import _cmd_vim
        assert _cmd_vim("/vim", None, MagicMock()) is True

    def test_search_provider_no_args(self):
        from terry.cli_commands import _cmd_search_provider
        assert _cmd_search_provider("/search-provider", None, MagicMock()) is True

    def test_login_command(self):
        from terry.cli_commands import _cmd_login
        assert _cmd_login("/login", None, MagicMock()) is True

    def test_logout_command(self):
        from terry.cli_commands import _cmd_logout
        assert _cmd_logout("/logout", None, MagicMock()) is True


# ═══════════════════════════════════════════════════════════════════
# AGENT SWARM — test swarm patterns
# ═══════════════════════════════════════════════════════════════════

class TestAgentSwarm:
    def test_import(self):
        from terry.core.agent_swarm import AgentSwarm
        assert AgentSwarm is not None

    def test_swarm_init(self):
        from terry.core.agent_swarm import AgentSwarm
        swarm = AgentSwarm(max_agents=10)
        assert swarm._max_agents == 10

    def test_swarm_scatter(self):
        from terry.core.agent_swarm import AgentSwarm
        swarm = AgentSwarm(max_agents=5)
        result = asyncio.run(swarm.scatter("test", count=2, timeout=5))
        assert result.stats["total"] == 2
        assert result.stats["done"] == 2

    def test_swarm_gather(self):
        from terry.core.agent_swarm import AgentSwarm
        swarm = AgentSwarm(max_agents=5)
        result = asyncio.run(swarm.gather(["task1", "task2"], timeout=5))
        assert result.stats["total"] == 2

    def test_swarm_gather_empty(self):
        from terry.core.agent_swarm import AgentSwarm
        result = asyncio.run(AgentSwarm().gather([]))
        assert result.stats["total"] == 0

    def test_swarm_task_tracking(self):
        from terry.core.agent_swarm import AgentSwarm
        swarm = AgentSwarm()
        asyncio.run(swarm.scatter("x", count=3, timeout=5))
        tasks = swarm.list_tasks()
        assert len(tasks) == 3

    def test_swarm_merge_dedup(self):
        from terry.core.agent_swarm import AgentSwarm
        assert AgentSwarm._merge_results(["a", "a", "b"]) == "a\n\n---\n\nb"
        assert AgentSwarm._merge_results([]) == ""

    def test_swarm_consensus(self):
        from terry.core.agent_swarm import AgentSwarm
        r = AgentSwarm._calc_consensus(["same", "same", "diff"])
        assert 0.6 < r < 0.7  # ~2/3
        assert AgentSwarm._calc_consensus([]) == 1.0  # empty = perfect agreement
