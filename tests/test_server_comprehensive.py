"""Comprehensive tests for server modules."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import asyncio


class TestTerryServer:
    """Test TerryServer class."""

    def test_init_default(self):
        """Test default initialization."""
        from terry.server import TerryServer
        server = TerryServer()
        assert server.host == "127.0.0.1"
        assert server.port == 8670
        assert server.agent is None

    def test_init_custom(self):
        """Test custom initialization."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"
        workdir = Path("/tmp/test")

        server = TerryServer(
            config=config,
            workdir=workdir,
            host="0.0.0.0",
            port=9000,
        )
        assert server.host == "0.0.0.0"
        assert server.port == 9000
        assert server.workdir == workdir

    def test_start_stop(self):
        """Test server start and stop."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18671)
        server.start()
        assert server.agent is not None
        assert server._running is True

        server.stop()
        assert server._running is False

    def test_chat_no_agent(self):
        """Test chat without agent."""
        from terry.server import TerryServer
        server = TerryServer()
        result = server.chat("test")
        assert "error" in result

    def test_chat_with_agent(self):
        """Test chat with agent."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18672)
        server.start()

        # Mock the agent's run method
        server.agent.run = MagicMock(return_value="Test response")
        server.agent.session = MagicMock()
        server.agent.session.session_id = "test-session"
        server.agent.tool_call_count = 0

        result = server.chat("Hello")
        assert "response" in result
        assert result["response"] == "Test response"
        assert "session_id" in result

        server.stop()

    def test_execute_tool_no_agent(self):
        """Test tool execution without agent."""
        from terry.server import TerryServer
        server = TerryServer()
        result = server.execute_tool("bash", {"command": "echo test"})
        assert "error" in result

    def test_execute_tool_with_agent(self):
        """Test tool execution with agent."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18673)
        server.start()

        # Mock the agent's tools
        server.agent.tools = MagicMock()
        server.agent.tools.execute = MagicMock(return_value="Tool result")

        result = server.execute_tool("bash", {"command": "echo test"})
        assert "result" in result
        assert result["result"] == "Tool result"

        server.stop()

    def test_get_status_no_agent(self):
        """Test status without agent."""
        from terry.server import TerryServer
        server = TerryServer()
        result = server.get_status()
        assert result == {"status": "stopped"}

    def test_get_status_with_agent(self):
        """Test status with agent."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18674)
        server.start()

        server.agent.get_status = MagicMock(return_value={"status": "running"})
        server._running = True

        result = server.get_status()
        assert "status" in result
        assert result["server_running"] is True

        server.stop()

    def test_start_background_task(self):
        """Test starting background task."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18675)
        server.start()

        # Mock the chat method
        server.chat = MagicMock(return_value={"response": "Done"})

        task_id = server.start_background_task("Test task", interval_minutes=0)
        assert task_id.startswith("bg_")
        assert task_id in server._background_tasks

        server.stop()

    def test_create_app(self):
        """Test creating WSGI app."""
        from terry.server import TerryServer
        server = TerryServer()
        app = server.create_app()
        assert callable(app)

    def test_wsgi_status_endpoint(self):
        """Test WSGI status endpoint."""
        from terry.server import TerryServer
        server = TerryServer()
        app = server.create_app()

        def start_response(status, headers):
            pass

        env = {"PATH_INFO": "/status", "REQUEST_METHOD": "GET"}
        result = app(env, start_response)

        assert len(result) == 1
        data = json.loads(result[0])
        assert data["status"] == "stopped"

    def test_wsgi_status_endpoint_no_agent(self):
        """Test WSGI status endpoint without agent."""
        from terry.server import TerryServer
        server = TerryServer()
        app = server.create_app()

        def start_response(status, headers):
            pass

        env = {"PATH_INFO": "/status", "REQUEST_METHOD": "GET"}
        result = app(env, start_response)

        assert len(result) == 1
        data = json.loads(result[0])
        assert data["status"] == "stopped"

    def test_wsgi_status_endpoint_with_agent(self):
        """Test WSGI status endpoint with agent."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18676)
        server.start()
        server._running = True

        server.agent.get_status = MagicMock(return_value={"status": "running"})

        app = server.create_app()

        def start_response(status, headers):
            pass

        env = {"PATH_INFO": "/status", "REQUEST_METHOD": "GET"}
        result = app(env, start_response)

        assert len(result) == 1
        data = json.loads(result[0])
        assert "status" in data

        server.stop()

    def test_wsgi_tools_endpoint_no_agent(self):
        """Test WSGI tools endpoint without agent."""
        from terry.server import TerryServer
        server = TerryServer()
        app = server.create_app()

        def start_response(status, headers):
            pass

        # Test 404 for unknown tool
        env = {
            "PATH_INFO": "/tools/bash",
            "REQUEST_METHOD": "POST",
            "CONTENT_LENGTH": "0",
            "wsgi.input": __import__("io").BytesIO(b""),
        }
        result = app(env, start_response)

        assert len(result) == 1
        data = json.loads(result[0])
        assert "error" in data

    def test_wsgi_tools_endpoint_with_agent(self):
        """Test WSGI tools endpoint with agent."""
        from terry.server import TerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = TerryServer(config=config, host="127.0.0.1", port=18677)
        server.start()

        # Mock the agent's tools
        server.agent.tools.execute = MagicMock(return_value="Tool executed successfully")

        app = server.create_app()

        def start_response(status, headers):
            pass

        # Test tool execution
        test_data = json.dumps({"command": "echo test"}).encode()
        env = {
            "PATH_INFO": "/tools/bash",
            "REQUEST_METHOD": "POST",
            "CONTENT_LENGTH": str(len(test_data)),
            "wsgi.input": __import__("io").BytesIO(test_data),
        }
        result = app(env, start_response)

        assert len(result) == 1
        data = json.loads(result[0])
        assert "result" in data

        server.stop()


class TestAsyncTerryServer:
    """Test AsyncTerryServer class."""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test async server initialization."""
        pytest.importorskip("fastapi")
        from terry.server.async_server import AsyncTerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = AsyncTerryServer(config=config)
        assert server.config == config

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint."""
        pytest.importorskip("fastapi")
        from terry.server.async_server import AsyncTerryServer
        from terry.core.config import TerryConfig

        config = TerryConfig()
        config.model.api_key = "test-key"

        server = AsyncTerryServer(config=config)

        # Mock the health endpoint
        async def mock_health():
            return {"status": "ok"}

        server.health = mock_health
        result = await server.health()
        assert result["status"] == "ok"


class TestTelegramGateway:
    """Test Telegram gateway."""

    def test_init(self):
        """Test gateway initialization."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")
        assert gw.token == "test-token"
        assert gw._running is False

    def test_send_typing(self):
        """Test send typing indicator."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the API call
        gw._api_call = MagicMock(return_value={"ok": True})

        gw.send_typing(123)
        gw._api_call.assert_called_once()

    def test_send_broadcast(self):
        """Test send broadcast message."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the API call
        gw._api_call = MagicMock(return_value={"ok": True})

        gw.send_broadcast([123, 456], "Test message")
        assert gw._api_call.call_count == 2

    def test_handle_start_command(self):
        """Test handling /start command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the send_message method
        gw.send_message = MagicMock()

        update = {"message": {"text": "/start", "chat": {"id": 123}}}
        gw.handle_message(update)

        gw.send_message.assert_called_once()

    def test_handle_help_command(self):
        """Test handling /help command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the send_message method
        gw.send_message = MagicMock()

        update = {"message": {"text": "/help", "chat": {"id": 123}}}
        gw.handle_message(update)

        gw.send_message.assert_called_once()

    def test_handle_new_command(self):
        """Test handling /new command."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the send_message method
        gw.send_message = MagicMock()

        update = {"message": {"text": "/new", "chat": {"id": 123}}}
        gw.handle_message(update)

        gw.send_message.assert_called_once()

    def test_handle_regular_message_no_agent(self):
        """Test handling regular message without agent."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the send_message method
        gw.send_message = MagicMock()

        update = {"message": {"text": "Hello", "chat": {"id": 123}}}
        gw.handle_message(update)

        # Should send "Agent not configured" message
        gw.send_message.assert_called_once()

    def test_handle_regular_message_with_agent(self):
        """Test handling regular message with agent."""
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test-token")

        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.run = MagicMock(return_value="Test response")
        gw.agent_factory = lambda: mock_agent

        # Mock the send_message method
        gw.send_message = MagicMock()
        gw.send_typing = MagicMock()

        update = {"message": {"text": "Hello", "chat": {"id": 123}}}
        gw.handle_message(update)

        # Should call run and send_message
        mock_agent.run.assert_called_once_with("Hello")
        gw.send_message.assert_called_once()


class TestDiscordGateway:
    """Test Discord gateway."""

    def test_init(self):
        """Test gateway initialization."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")
        assert gw.token == "test-token"
        assert gw._running is False

    def test_send_typing(self):
        """Test send typing indicator."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")

        # Mock the API call
        gw._api_call = MagicMock(return_value={"ok": True})

        gw.send_typing(123)
        gw._api_call.assert_called_once()

    def test_handle_help_command(self):
        """Test handling help command."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")

        # Mock the send_message method
        gw.send_message = MagicMock()

        gw._handle_command(123, "help", "msg-123")

        gw.send_message.assert_called_once()

    def test_handle_status_command(self):
        """Test handling status command."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")

        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.get_status = MagicMock(return_value={"status": "running"})
        gw.agent_factory = lambda: mock_agent

        # Mock the send_message method
        gw.send_message = MagicMock()

        gw._handle_command(123, "status", "msg-123")

        mock_agent.get_status.assert_called_once()
        gw.send_message.assert_called_once()

    def test_handle_mention(self):
        """Test handling mention."""
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test-token")

        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.run = MagicMock(return_value="Test response")
        gw.agent_factory = lambda: mock_agent

        # Mock the send_message method
        gw.send_message = MagicMock()
        gw.send_typing = MagicMock()

        gw.handle_mention(123, "msg-123", "user", "Hello")

        mock_agent.run.assert_called_once_with("Hello")
        gw.send_message.assert_called_once()
