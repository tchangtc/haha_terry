"""Comprehensive tests for core modules with low coverage."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════
# ASYNC LLM CLIENT
# ═══════════════════════════════════════════════════════════════════

class TestAsyncLLMClientDetailed:
    """Deep tests for async LLM client."""

    @pytest.mark.asyncio
    async def test_anthropic_chat(self):
        """Test Anthropic chat endpoint."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig

        config = ModelConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello from Claude!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        response = await client.chat(messages)

        assert response["content"][0]["text"] == "Hello from Claude!"
        assert response["stop_reason"] == "end_turn"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_openai_chat(self):
        """Test OpenAI chat endpoint."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig

        config = ModelConfig(
            provider="openai",
            model="gpt-4o",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello from GPT!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        response = await client.chat(messages)

        assert response["content"][0]["text"] == "Hello from GPT!"
        assert response["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_anthropic_streaming(self):
        """Test Anthropic streaming."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig

        config = ModelConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)

        # Mock streaming response - need proper async context manager with aiter_lines
        class MockStreamResponse:
            def __init__(self):
                self.lines = [
                    'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}}',
                    'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "world!"}}',
                    'data: [DONE]',
                ]
                self.index = 0

            def raise_for_status(self):
                pass

            async def aiter_lines(self):
                for line in self.lines:
                    yield line

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=MockStreamResponse())
        client._client = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        chunks = []
        async for chunk in client.chat_stream(messages):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == "Hello "
        assert chunks[1] == "world!"

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test client cleanup."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig

        config = ModelConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)

        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        client._client = mock_client

        await client.close()
        mock_client.aclose.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# ASYNC AGENT
# ═══════════════════════════════════════════════════════════════════

class TestAsyncAgentDetailed:
    """Deep tests for async agent."""

    @pytest.mark.asyncio
    async def test_simple_response(self):
        """Test simple LLM response without tools."""
        from terry.core.async_agent import AsyncAgent
        from terry.core.config import TerryConfig
        from terry.core.async_llm import AsyncLLMClient

        config = TerryConfig()
        config.model.api_key = "test-key"

        async_llm = AsyncLLMClient(config.model)
        mock_client = AsyncMock()

        # Mock LLM response (no tools)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "I can help with that!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 15},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        async_llm._client = mock_client

        agent = AsyncAgent(
            config=config,
            tools=[],
            system_prompt="You are helpful.",
            async_llm=async_llm,
            tool_executor=MagicMock(),
        )

        messages = [{"role": "user", "content": "Help me"}]
        response = await agent.run(messages)

        assert "I can help" in response

    @pytest.mark.asyncio
    async def test_tool_call_loop(self):
        """Test agent with tool calls."""
        from terry.core.async_agent import AsyncAgent
        from terry.core.config import TerryConfig
        from terry.core.async_llm import AsyncLLMClient

        config = TerryConfig()
        config.model.api_key = "test-key"

        async_llm = AsyncLLMClient(config.model)
        mock_client = AsyncMock()

        # First response: tool call
        tool_response = MagicMock()
        tool_response.json.return_value = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "read_file",
                    "input": {"path": "test.py"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        tool_response.raise_for_status = MagicMock()

        # Second response: final answer
        final_response = MagicMock()
        final_response.json.return_value = {
            "content": [{"type": "text", "text": "File contains X"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 30, "output_tokens": 10},
        }
        final_response.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(side_effect=[tool_response, final_response])
        async_llm._client = mock_client

        tool_executor = MagicMock(return_value="file content")

        agent = AsyncAgent(
            config=config,
            tools=[{"name": "read_file", "description": "Read file"}],
            system_prompt="You are helpful.",
            async_llm=async_llm,
            tool_executor=tool_executor,
        )

        messages = [{"role": "user", "content": "Read test.py"}]
        response = await agent.run(messages)

        assert "File contains X" in response
        tool_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        """Test max iterations limit."""
        from terry.core.async_agent import AsyncAgent
        from terry.core.config import TerryConfig
        from terry.core.async_llm import AsyncLLMClient

        config = TerryConfig()
        config.model.api_key = "test-key"

        async_llm = AsyncLLMClient(config.model)
        mock_client = AsyncMock()

        # Always return tool call
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {"type": "tool_use", "id": "tool_1", "name": "bash", "input": {}}
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        async_llm._client = mock_client

        agent = AsyncAgent(
            config=config,
            tools=[{"name": "bash"}],
            system_prompt="Test",
            async_llm=async_llm,
            tool_executor=MagicMock(),
            max_iterations=3,
        )

        messages = [{"role": "user", "content": "test"}]
        response = await agent.run(messages)

        assert "Maximum iterations" in response


# ═══════════════════════════════════════════════════════════════════
# ASYNC HARNESS
# ═══════════════════════════════════════════════════════════════════

class TestAsyncHarnessDetailed:
    """Deep tests for async harness."""

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test parallel pattern execution."""
        from terry.core.async_harness import AsyncHarnessEngine

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(side_effect=["Result 1", "Result 2", "Result 3"])
        mock_agent.get_metrics_summary = MagicMock(return_value={
            "counters": {"input_tokens": 100, "output_tokens": 50}
        })

        engine = AsyncHarnessEngine(
            agent_factory=lambda: mock_agent,
            max_concurrent=5,
        )

        result = await engine.execute(
            pattern="parallel",
            prompts=["Task 1", "Task 2", "Task 3"],
            timeout=5.0,
        )

        assert result["parallel_tasks"] == 3
        assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_adversarial_verify_passed(self):
        """Test adversarial verify pattern with passing result."""
        from terry.core.async_harness import AsyncHarnessEngine

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(side_effect=[
            "Solution code",
            "PASS - looks good",
        ])

        engine = AsyncHarnessEngine(
            agent_factory=lambda: mock_agent,
            max_concurrent=1,
        )

        result = await engine.execute(
            pattern="adversarial-verify",
            goals=["Fix bug"],
            timeout=5.0,
        )

        assert result["status"] == "passed"
        assert "solution" in result
        assert "verdict" in result

    @pytest.mark.asyncio
    async def test_adversarial_verify_failed(self):
        """Test adversarial verify pattern with failing result."""
        from terry.core.async_harness import AsyncHarnessEngine

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(side_effect=[
            "Solution code",
            "FAIL - issues found",
            "Fixed solution",
        ])

        engine = AsyncHarnessEngine(
            agent_factory=lambda: mock_agent,
            max_concurrent=1,
        )

        result = await engine.execute(
            pattern="adversarial-verify",
            goals=["Fix bug"],
            timeout=5.0,
        )

        assert result["status"] == "fixed"
        assert "original" in result
        assert "fix" in result

    @pytest.mark.asyncio
    async def test_tournament_pattern(self):
        """Test tournament pattern."""
        from terry.core.async_harness import AsyncHarnessEngine

        mock_agent = MagicMock()
        # 3 solutions + 3 comparisons
        mock_agent.arun = AsyncMock(side_effect=[
            "Solution A",
            "Solution B",
            "Solution C",
            "A",  # A vs B
            "A",  # A vs C
            "B",  # B vs C
        ])

        engine = AsyncHarnessEngine(
            agent_factory=lambda: mock_agent,
            max_concurrent=3,
        )

        result = await engine.execute(
            pattern="tournament",
            prompts=["Approach A", "Approach B", "Approach C"],
            timeout=5.0,
        )

        assert "winner_index" in result
        assert "scores" in result
        assert result["winner_index"] == 0  # A wins with 2 points


# ═══════════════════════════════════════════════════════════════════
# ASYNC SUBAGENT MANAGER
# ═══════════════════════════════════════════════════════════════════

class TestAsyncSubAgentManagerDetailed:
    """Deep tests for async sub-agent manager."""

    @pytest.mark.asyncio
    async def test_cancel_running_agent(self):
        """Test cancelling a running sub-agent."""
        from terry.core.async_subagent import AsyncSubAgentManager, AsyncSubAgentStatus

        # Create agent that takes time
        async def slow_agent(*args, **kwargs):
            await asyncio.sleep(10)
            return "done"

        mock_agent = MagicMock()
        mock_agent.arun = slow_agent

        manager = AsyncSubAgentManager(
            agent_factory=lambda: mock_agent,
            max_concurrent=5,
        )
        await manager.start()

        agent_id = await manager.spawn("Long task", timeout=1.0)
        await asyncio.sleep(0.1)

        # Cancel it
        cancelled = await manager.cancel(agent_id)
        assert cancelled is True

        status = manager.get_status(agent_id)
        assert status["status"] == AsyncSubAgentStatus.CANCELLED.value

        await manager.stop()

    @pytest.mark.asyncio
    async def test_run_parallel_prompts(self):
        """Test running multiple prompts in parallel."""
        from terry.core.async_subagent import AsyncSubAgentManager

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(side_effect=["Result 1", "Result 2"])

        manager = AsyncSubAgentManager(
            agent_factory=lambda: mock_agent,
            max_concurrent=5,
        )
        await manager.start()

        results = await manager.run_parallel(
            prompts=["Task 1", "Task 2"],
            timeout=5.0,
        )

        assert len(results) == 2
        assert results["0"] == "Result 1"
        assert results["1"] == "Result 2"

        await manager.stop()

    @pytest.mark.asyncio
    async def test_run_sequential_prompts(self):
        """Test running prompts sequentially."""
        from terry.core.async_subagent import AsyncSubAgentManager

        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(side_effect=["Result 1", "Result 1\n\nResult 2"])

        manager = AsyncSubAgentManager(
            agent_factory=lambda: mock_agent,
            max_concurrent=1,
        )
        await manager.start()

        results = await manager.run_sequential(
            prompts=["Task 1", "Task 2"],
            timeout=5.0,
        )

        assert len(results) == 2

        await manager.stop()


# ═══════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════

class TestCLICommandsDetailed:
    """Test CLI command handlers."""

    def test_help_command(self):
        """Test /help command."""
        from terry.cli_commands import _cmd_help
        from unittest.mock import MagicMock

        agent = MagicMock()
        result = _cmd_help("/help", None, agent)
        assert result is True

    def test_new_command(self):
        """Test /new command."""
        from terry.cli_commands import _cmd_new
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.reset = MagicMock()
        result = _cmd_new("/new", None, agent)
        assert result is True
        agent.reset.assert_called_once()

    def test_mode_command_cycle(self):
        """Test /mode cycle command."""
        from terry.cli_commands import _cmd_mode
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.cycle_mode = MagicMock(return_value="auto")
        result = _cmd_mode("/mode", None, agent)
        assert result is True

    def test_mode_command_set(self):
        """Test /mode set command."""
        from terry.cli_commands import _cmd_mode
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.set_mode = MagicMock(return_value=True)
        result = _cmd_mode("/mode", "auto", agent)
        assert result is True
        agent.set_mode.assert_called_once_with("auto")

    def test_tools_command(self):
        """Test /tools command."""
        from terry.cli_commands import _cmd_tools
        from unittest.mock import MagicMock

        agent = MagicMock()
        tool = MagicMock()
        tool.name = "bash"
        tool.description = "Run bash"
        agent.tools.list_tools = MagicMock(return_value=[tool])
        result = _cmd_tools("/tools", None, agent)
        assert result is True

    def test_permissions_command(self):
        """Test /permissions command."""
        from terry.cli_commands import _cmd_permissions
        from unittest.mock import MagicMock

        agent = MagicMock()
        agent.permission_store.list_rules = MagicMock(return_value=[])
        agent.permission_level.value = "medium"
        result = _cmd_permissions("/permissions", None, agent)
        assert result is True


# ═══════════════════════════════════════════════════════════════════
# GATEWAYS
# ═══════════════════════════════════════════════════════════════════

class TestTelegramGatewayDetailed:
    """Test Telegram gateway."""

    def test_handle_start_command(self):
        """Test /start command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")
        update = {
            "message": {
                "text": "/start",
                "chat": {"id": 123},
            }
        }

        gw.handle_message(update)
        # Should send welcome message

    def test_handle_help_command(self):
        """Test /help command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")
        update = {
            "message": {
                "text": "/help",
                "chat": {"id": 123},
            }
        }

        gw.handle_message(update)

    def test_handle_new_command(self):
        """Test /new command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")
        update = {
            "message": {
                "text": "/new",
                "chat": {"id": 123},
            }
        }

        gw.handle_message(update)


class TestDiscordGatewayDetailed:
    """Test Discord gateway."""

    def test_handle_help_command(self):
        """Test help command."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")
        gw._handle_command(123, "help", "msg_123")

    def test_handle_status_command(self):
        """Test status command."""
        from terry.server.gateways.discord_gateway import DiscordGateway
        from unittest.mock import MagicMock

        gw = DiscordGateway(token="test-token")
        mock_agent = MagicMock()
        mock_agent.get_status = MagicMock(return_value={"status": "running"})
        gw.agent_factory = lambda: mock_agent
        gw._handle_command(123, "status", "msg_123")


# ═══════════════════════════════════════════════════════════════════
# DYNAMIC WORKFLOW
# ═══════════════════════════════════════════════════════════════════

class TestDynamicWorkflowDetailed:
    """Test dynamic workflow patterns."""

    def test_fan_out_merge_pattern(self):
        """Test fan-out-merge pattern."""
        from terry.core.dynamic_workflow import DynamicWorkflowEngine, WorkflowPattern

        mock_agent = MagicMock()
        mock_agent.run = MagicMock(side_effect=[
            "Result 1",
            "Result 2",
            "Merged result",
        ])

        engine = DynamicWorkflowEngine(
            agent_factory=lambda: mock_agent,
        )

        workflow = engine.plan_workflow(
            goal="Analyze codebase",
            pattern=WorkflowPattern.FAN_OUT_MERGE,
        )

        assert workflow.pattern == WorkflowPattern.FAN_OUT_MERGE
        assert len(workflow.stages) > 0


# ═══════════════════════════════════════════════════════════════════
# HELPER CLASSES
# ═══════════════════════════════════════════════════════════════════

class AsyncContextManager:
    """Helper for mocking async context managers."""

    def __init__(self, async_gen):
        self.async_gen = async_gen

    async def __aenter__(self):
        return self.async_gen()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
