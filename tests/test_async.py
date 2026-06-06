"""Async functionality tests — verify true async implementation."""

from __future__ import annotations

import asyncio

import pytest


class TestAsyncLLMClient:
    """Test async LLM client."""

    def test_import(self):
        """Verify async LLM client can be imported."""
        from terry.core.async_llm import AsyncLLMClient
        assert AsyncLLMClient is not None

    def test_initialization(self):
        """Test client initialization."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig

        config = ModelConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)
        assert client.config == config
        assert client.provider_type == "anthropic"


class TestAsyncAgent:
    """Test async agent."""

    def test_import(self):
        """Verify async agent can be imported."""
        from terry.core.async_agent import AsyncAgent
        assert AsyncAgent is not None

    @pytest.mark.asyncio
    async def test_arun_method_exists(self):
        """Test that run method exists and is async."""
        from terry.core.async_agent import AsyncAgent
        from terry.core.config import TerryConfig
        from terry.core.async_llm import AsyncLLMClient
        from unittest.mock import MagicMock

        config = TerryConfig()
        config.model.api_key = "test-key"

        # Create mock LLM
        async_llm = AsyncLLMClient(config.model)

        # Create async agent with correct parameters
        agent = AsyncAgent(
            config=config,
            tools=[],
            system_prompt="You are a helpful assistant.",
            async_llm=async_llm,
            tool_executor=MagicMock(),
        )

        assert hasattr(agent, "run")
        assert asyncio.iscoroutinefunction(agent.run)


class TestAsyncHarness:
    """Test async harness."""

    def test_import(self):
        """Verify async harness can be imported."""
        from terry.core.async_harness import AsyncHarnessEngine, AsyncHarnessPattern
        assert AsyncHarnessEngine is not None
        assert AsyncHarnessPattern is not None

    def test_patterns(self):
        """Test all harness patterns exist."""
        from terry.core.async_harness import AsyncHarnessPattern

        patterns = [
            "sequential",
            "parallel",
            "fan_out_merge",
            "adversarial_verify",
            "tournament",
            "classify_execute",
            "loop_until_done",
            "generate_filter",
        ]

        for pattern in patterns:
            assert hasattr(AsyncHarnessPattern, pattern.upper())

    @pytest.mark.asyncio
    async def test_execute_method_is_async(self):
        """Test that execute method is async."""
        from terry.core.async_harness import AsyncHarnessEngine
        from unittest.mock import MagicMock

        engine = AsyncHarnessEngine(
            agent_factory=MagicMock,
            max_concurrent=5,
        )

        assert hasattr(engine, "execute")
        assert asyncio.iscoroutinefunction(engine.execute)


class TestAsyncSubAgentManager:
    """Test async sub-agent manager."""

    def test_import(self):
        """Verify async sub-agent manager can be imported."""
        from terry.core.async_subagent import AsyncSubAgentManager, AsyncSubAgent
        assert AsyncSubAgentManager is not None
        assert AsyncSubAgent is not None

    @pytest.mark.asyncio
    async def test_spawn_method_is_async(self):
        """Test that spawn method is async."""
        from terry.core.async_subagent import AsyncSubAgentManager
        from unittest.mock import MagicMock

        manager = AsyncSubAgentManager(
            agent_factory=MagicMock,
            max_concurrent=10,
        )

        assert hasattr(manager, "spawn")
        assert asyncio.iscoroutinefunction(manager.spawn)

    @pytest.mark.asyncio
    async def test_wait_method_is_async(self):
        """Test that wait method is async."""
        from terry.core.async_subagent import AsyncSubAgentManager
        from unittest.mock import MagicMock

        manager = AsyncSubAgentManager(
            agent_factory=MagicMock,
            max_concurrent=10,
        )

        assert hasattr(manager, "wait")
        assert asyncio.iscoroutinefunction(manager.wait)


class TestAsyncServer:
    """Test async server (requires FastAPI)."""

    def test_import_with_fastapi(self):
        """Test async server import (requires FastAPI installed)."""
        try:
            from terry.server.async_server import AsyncTerryServer
            assert AsyncTerryServer is not None
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_server_has_async_methods(self):
        """Test that server has async methods."""
        try:
            from terry.server.async_server import AsyncTerryServer
            from terry.core.config import TerryConfig

            config = TerryConfig()
            config.model.api_key = "test-key"

            server = AsyncTerryServer(config=config)

            assert hasattr(server, "start")
            assert asyncio.iscoroutinefunction(server.start)
        except ImportError:
            pytest.skip("FastAPI not installed")


class TestAsyncIntegration:
    """Integration tests for async components."""

    @pytest.mark.asyncio
    async def test_async_llm_chat_mock(self):
        """Test async LLM chat with mock."""
        from terry.core.async_llm import AsyncLLMClient
        from terry.core.config import ModelConfig
        from unittest.mock import MagicMock, AsyncMock

        config = ModelConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
        )
        client = AsyncLLMClient(config)

        # Mock the httpx client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._client = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        response = await client.chat(messages)

        assert "content" in response
        assert "stop_reason" in response
        assert response["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_async_subagent_spawn_and_wait(self):
        """Test spawning and waiting for async sub-agent."""
        from terry.core.async_subagent import AsyncSubAgentManager
        from unittest.mock import MagicMock, AsyncMock

        # Create mock agent factory
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value="Task completed")

        manager = AsyncSubAgentManager(
            agent_factory=lambda: mock_agent,
            max_concurrent=5,
        )
        await manager.start()

        # Spawn sub-agent
        agent_id = await manager.spawn("Complete task", timeout=5.0)
        assert agent_id is not None
        assert isinstance(agent_id, str)

        # Wait for completion
        result = await manager.wait(agent_id, timeout=5.0)
        assert result == "Task completed"

        await manager.stop()

    @pytest.mark.asyncio
    async def test_async_harness_sequential(self):
        """Test async harness sequential execution."""
        from terry.core.async_harness import AsyncHarnessEngine
        from unittest.mock import MagicMock, AsyncMock

        # Create mock agent factory
        mock_agent = MagicMock()
        mock_agent.arun = AsyncMock(return_value="Result")
        mock_agent.get_metrics_summary = MagicMock(return_value={
            "counters": {"input_tokens": 100, "output_tokens": 50}
        })

        engine = AsyncHarnessEngine(
            agent_factory=lambda: mock_agent,
            max_concurrent=5,
        )

        result = await engine.execute(
            pattern="sequential",
            prompts=["Task 1", "Task 2"],
            timeout=5.0,
        )

        assert "results" in result
        assert "steps_completed" in result
        assert result["steps_completed"] == 2
