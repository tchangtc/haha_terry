"""End-to-end tests with mock LLM — validates complete Agent loop behavior."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from terry.core.config import TerryConfig
from terry.core.agent import Agent


class MockLLMResponse:
    """Factory for mock LLM responses."""

    @staticmethod
    def text_response(content: str) -> dict:
        return {
            "content": [type("Block", (), {"type": "text", "text": content})()],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }

    @staticmethod
    def tool_response(tool_name: str, tool_input: dict) -> dict:
        return {
            "content": [
                type("Block", (), {"type": "tool_use", "name": tool_name, "input": tool_input, "id": "tool_001"})()
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 15},
        }


class TestE2EAgentLoop:
    """End-to-end tests: full Agent.run() cycle with mocked LLM."""

    def test_simple_text_response(self):
        """Agent receives text response → returns it to user."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        with patch.object(agent.llm, "chat") as mock_chat:
            mock_chat.return_value = MockLLMResponse.text_response("Hello! I found the code.")
            response = agent.run("Find the auth logic")

        assert "Hello!" in response
        assert mock_chat.call_count == 1
        assert agent.tool_call_count == 0

    def test_tool_call_loop(self):
        """Agent calls tool → gets result → loops back → returns final."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        call_count = [0]

        def mock_chat_side_effect(messages=None, system=None, tools=None, max_tokens=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: ask to read file
                return MockLLMResponse.tool_response("read_file", {"path": "auth.py", "limit": 50})
            else:
                # Second call: done
                return MockLLMResponse.text_response("I found the auth logic in auth.py:45")

        with patch.object(agent.llm, "chat", side_effect=mock_chat_side_effect):
            response = agent.run("Find the auth logic")

        assert "auth.py" in response
        assert call_count[0] >= 2
        assert agent.tool_call_count >= 1

    def test_multi_tool_sequence(self):
        """Agent executes grep → read_file → edit_file sequence."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        import tempfile
        with tempfile.TemporaryDirectory() as d:
            agent.workdir = Path(d)
            # Create a test file
            (Path(d) / "test.py").write_text("def foo():\n    return 'bar'\n")

            step = [0]

            def side_effect(messages=None, system=None, tools=None, max_tokens=None, **kwargs):
                step[0] += 1
                if step[0] == 1:
                    return MockLLMResponse.tool_response("grep", {"pattern": "def foo", "path": "."})
                elif step[0] == 2:
                    return MockLLMResponse.tool_response("read_file", {"path": "test.py"})
                else:
                    return MockLLMResponse.text_response("Found and reviewed test.py. The function foo returns 'bar'.")

            with patch.object(agent.llm, "chat", side_effect=side_effect):
                response = agent.run("Find function foo")

            assert "foo" in response.lower()
            assert agent.tool_call_count >= 2

    def test_tool_budget_exceeded(self):
        """Agent hits max tool calls → forced wrap-up."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        config.max_tool_calls = 2
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        def infinite_tools(messages=None, system=None, tools=None, max_tokens=None, **kwargs):
            return MockLLMResponse.tool_response("read_file", {"path": "file.py"})

        with patch.object(agent.llm, "chat", side_effect=infinite_tools):
            response = agent.run("Read everything")

        # Should have wrapped up after max_tool_calls
        assert agent.tool_call_count <= 3  # max_tool_calls=2 + wrap_up

    def test_error_recovery_mock(self):
        """Agent recovers from LLM error → retries → succeeds."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        attempt = [0]

        def retry_then_succeed(messages=None, system=None, tools=None, max_tokens=None, **kwargs):
            attempt[0] += 1
            if attempt[0] <= 2:
                raise Exception("rate limit exceeded")
            return MockLLMResponse.text_response("Recovered and working!")

        with patch.object(agent.llm, "chat", side_effect=retry_then_succeed):
            response = agent.run("Hello")

        assert "Recovered" in response

    def test_agent_reset(self):
        """Agent.reset() clears messages and tool count."""
        config = TerryConfig()
        config.model.api_key = "test-key"
        agent = Agent(config, enable_subagents=False, enable_skills=False,
                      enable_memory=False, enable_session=False,
                      enable_metrics=False, enable_cache=False,
                      enable_checkpoint=False, enable_planner=False)

        agent.messages = [{"role": "user", "content": "test"}]
        agent.tool_call_count = 10
        agent.reset()
        assert len(agent.messages) == 0
        assert agent.tool_call_count == 0
