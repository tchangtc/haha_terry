"""Phase 4 coverage push — tests for previously untested modules:
- MCP client
- LSP client
- Desktop launcher
- WebUI server internals
- Gateway modules
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ══════════════════════════════════════════════════════════════════════
# MCP Client Tests
# ══════════════════════════════════════════════════════════════════════

class TestMCPToolWrapper:
    """Test MCPToolWrapper — wraps external MCP tools as Terry tools."""

    def test_init_with_minimal_tool(self):
        from terry.mcp import MCPToolWrapper

        tool = MCPToolWrapper({"name": "hello", "description": "Say hello"})
        assert tool.name == "mcp_hello"
        assert tool.description == "Say hello"
        assert tool.input_schema == {"type": "object", "properties": {}, "required": []}
        assert tool._mcp_tool == {"name": "hello", "description": "Say hello"}

    def test_init_with_full_tool_schema(self):
        from terry.mcp import MCPToolWrapper

        schema = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }
        tool = MCPToolWrapper({
            "name": "echo",
            "description": "Echo back",
            "inputSchema": schema,
        })
        assert tool.input_schema == schema
        assert len(tool.input_schema["required"]) == 1

    def test_execute_without_server(self):
        from terry.mcp import MCPToolWrapper

        tool = MCPToolWrapper({"name": "test_tool"})
        result = tool.execute(arg="value")
        assert "Error" in result
        assert "not connected" in result

    def test_execute_with_mock_server(self):
        from terry.mcp import MCPToolWrapper

        mock_server = MagicMock()
        mock_server.call_tool.return_value = "Tool executed successfully"

        tool = MCPToolWrapper({"name": "mock_tool", "description": "Mock"}, server=mock_server)
        result = tool.execute(param="test")

        assert result == "Tool executed successfully"
        mock_server.call_tool.assert_called_once_with("mock_tool", {"param": "test"})

    def test_execute_with_server_error(self):
        from terry.mcp import MCPToolWrapper

        mock_server = MagicMock()
        mock_server.call_tool.side_effect = RuntimeError("Server crashed")

        tool = MCPToolWrapper({"name": "buggy"}, server=mock_server)
        result = tool.execute()

        assert "Error" in result
        assert "Server crashed" in result

    def test_name_default_for_unnamed_tool(self):
        from terry.mcp import MCPToolWrapper

        tool = MCPToolWrapper({})
        assert tool.name == "mcp_unknown"


class TestMCPClient:
    """Test MCPClient — connects to external MCP servers."""

    def test_init(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        assert client.connections == {}
        assert client.wrapped_tools == []

    def test_list_connections_empty(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        assert client.list_connections() == []

    def test_connect_sse_mocked(self):
        from terry.mcp import MCPClient

        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            client = MCPClient()
            result = client.connect_sse("test_sse", "https://example.com/sse")

            assert result is True
            assert "test_sse" in client.connections
            assert client.connections["test_sse"]["type"] == "sse"
            assert client.list_connections()[0]["name"] == "test_sse"

    def test_connect_sse_fails_gracefully(self):
        from terry.mcp import MCPClient

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            client = MCPClient()
            result = client.connect_sse("bad", "https://invalid/sse")

            # connect_sse registers connection before doing httpx.get,
            # but the exception causes the connection registration to remain.
            # The function correctly returns False on error.
            assert result is False

    def test_connect_stdio_fails_without_command(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        result = client.connect_stdio("test", "/nonexistent/command")
        assert result is False

    def test_register_tools_unknown_connection(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        count = client.register_tools("nonexistent")
        assert count == 0

    def test_register_tools_known_connection(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        client.connections["test"] = {"type": "sse", "url": "http://example.com"}
        count = client.register_tools("test")
        assert count == 0  # No tools pre-registered

    def test_disconnect_unknown(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        assert client.disconnect("nonexistent") is False

    def test_disconnect_sse(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        client.connections["sse_conn"] = {"type": "sse", "url": "http://example.com"}
        assert client.disconnect("sse_conn") is True
        assert "sse_conn" not in client.connections

    def test_disconnect_stdio_terminates_process(self):
        from terry.mcp import MCPClient

        mock_process = MagicMock()
        client = MCPClient()
        client.connections["stdio_conn"] = {
            "type": "stdio",
            "process": mock_process,
        }
        assert client.disconnect("stdio_conn") is True
        mock_process.terminate.assert_called_once()
        assert "stdio_conn" not in client.connections

    def test_multiple_connections(self):
        from terry.mcp import MCPClient

        client = MCPClient()
        client.connections["a"] = {"type": "sse", "url": "http://a.com"}
        client.connections["b"] = {"type": "sse", "url": "http://b.com"}

        conns = client.list_connections()
        assert len(conns) == 2
        assert {c["name"] for c in conns} == {"a", "b"}


# ══════════════════════════════════════════════════════════════════════
# LSP Client Tests
# ══════════════════════════════════════════════════════════════════════

class TestLSPClient:
    """Test LSPClient — language server protocol integration."""

    def test_init_defaults(self):
        from terry.lsp import LSPClient

        client = LSPClient()
        assert client.language == "python"
        assert client._process is None
        assert client._initialized is False
        assert client._id_counter == 0
        assert client.root_uri is not None
        assert client.root_uri.startswith("file://")

    def test_init_custom_language(self):
        from terry.lsp import LSPClient

        client = LSPClient(language="typescript")
        assert client.language == "typescript"

    def test_init_custom_root_uri(self):
        from terry.lsp import LSPClient

        client = LSPClient(root_uri="file:///custom/path")
        assert client.root_uri == "file:///custom/path"

    def test_lsp_commands_known_languages(self):
        from terry.lsp import LSPClient

        assert "python" in LSPClient.LSP_COMMANDS
        assert "typescript" in LSPClient.LSP_COMMANDS
        assert "rust" in LSPClient.LSP_COMMANDS
        assert "pyright-langserver" in LSPClient.LSP_COMMANDS["python"]

    def test_stop_when_not_started(self):
        from terry.lsp import LSPClient

        client = LSPClient()
        client.stop()  # Should not raise
        assert client._initialized is False

    def test_get_diagnostics_when_not_initialized(self):
        from terry.lsp import LSPClient

        client = LSPClient()
        diags = client.get_diagnostics("/nonexistent/file.py")
        assert diags == []

    def test_get_hover_when_not_initialized(self):
        from terry.lsp import LSPClient

        client = LSPClient()
        result = client.get_hover("/nonexistent/file.py", 0, 0)
        assert result is None

    def test_get_definition_when_not_initialized(self):
        from terry.lsp import LSPClient

        client = LSPClient()
        result = client.get_definition("/nonexistent/file.py", 0, 0)
        assert result is None

    def test_start_fails_for_unsupported_language(self):
        from terry.lsp import LSPClient

        client = LSPClient(language="brainfuck")
        assert client.start() is False
        assert client._initialized is False

    def test_start_fails_for_missing_command(self):
        from terry.lsp import LSPClient

        client = LSPClient(
            language="python",
            root_uri="file:///tmp",
        )
        # Override LSP_COMMANDS to use non-existent binary
        with patch.dict(client.LSP_COMMANDS, {"python": ["/nonexistent-lsp-xyz"]}):
            result = client.start()
            assert result is False

    def test_start_success_mocked(self):
        from terry.lsp import LSPClient

        client = LSPClient(language="python")
        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        # Simulate reading the initialize response
        mock_process.stdout.readline.side_effect = [
            "Content-Length: 45\r\n",
            "\r\n",
            '{"jsonrpc":"2.0","id":1,"result":{"capabilities":{}}}',
        ]

        with patch("subprocess.Popen", return_value=mock_process):
            result = client.start()
            assert result is True
            assert client._initialized is True

    def test_stop_terminates_process(self):
        from terry.lsp import LSPClient

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()

        client = LSPClient()
        client._process = mock_process
        client._initialized = True

        client.stop()

        assert client._initialized is False
        assert client._process is None
        mock_process.terminate.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
# Desktop Tests
# ══════════════════════════════════════════════════════════════════════

class TestDesktop:
    """Test desktop launcher module."""

    def test_open_browser_function(self):
        from terry.desktop import open_browser

        with patch("webbrowser.open") as mock_open:
            open_browser()
            mock_open.assert_called_once_with("http://127.0.0.1:8670")

    def test_open_browser_custom_url(self):
        from terry.desktop import open_browser

        with patch("webbrowser.open") as mock_open:
            open_browser("http://localhost:9999")
            mock_open.assert_called_once_with("http://localhost:9999")

    def test_start_browser_only_imports(self):
        """Verify start_browser_only is importable and returns a function."""
        from terry.desktop import start_browser_only
        assert callable(start_browser_only)


# ══════════════════════════════════════════════════════════════════════
# WebUI Server Tests
# ══════════════════════════════════════════════════════════════════════

class TestWebUIChatSession:
    """Test ChatSession used by WebUI server."""

    def test_create_session(self):
        from terry.webui.server import ChatSession

        session = ChatSession("test123")
        assert session.id == "test123"
        assert session.messages == []
        assert session.created_at > 0

    def test_add_message(self):
        from terry.webui.server import ChatSession

        session = ChatSession("s1")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
        assert session.messages[1]["role"] == "assistant"

    def test_to_dict(self):
        from terry.webui.server import ChatSession

        session = ChatSession("s1")
        session.add_message("user", "Test")

        d = session.to_dict()
        assert d["id"] == "s1"
        assert len(d["messages"]) == 1
        assert d["message_count"] == 1


class TestWebUISSEConnection:
    """Test SSEConnection for Server-Sent Events."""

    def test_init(self):
        from terry.webui.server import SSEConnection

        conn = SSEConnection()
        assert conn.active is True

    def test_send_event(self):
        from terry.webui.server import SSEConnection
        import queue

        conn = SSEConnection()
        conn.send("test_event", {"key": "value"})

        msg = conn.queue.get(timeout=1)
        assert "event: test_event" in msg
        assert '"key"' in msg
        assert '"value"' in msg

    def test_close(self):
        from terry.webui.server import SSEConnection

        conn = SSEConnection()
        assert conn.active is True
        conn.close()
        assert conn.active is False


class TestWebUIServerInit:
    """Test WebUIServer initialization and configuration."""

    def test_init_default(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999)
        assert server.host == "127.0.0.1"
        assert server.port == 9999
        assert server._running is False
        assert server.sessions == {}
        assert server.sse_connections == {}
        assert server.security is not None  # Security enabled by default

    def test_init_with_security_disabled(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999, enable_security=False)
        assert server.security is None

    def test_init_with_api_key(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999, api_key="secret-key")
        assert server.security is not None
        assert server.security.api_auth.is_enabled() is True

    def test_init_with_custom_rate_limit(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999, rate_limit=50, rate_window=30)
        assert server.security is not None
        assert server.security.rate_limiter.max_requests == 50
        assert server.security.rate_limiter.window_seconds == 30

    def test_get_or_create_session(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999)

        s1 = server._get_or_create_session()
        assert s1.id in server.sessions
        assert len(server.sessions) == 1

        s2 = server._get_or_create_session()
        assert len(server.sessions) == 2
        assert s1.id != s2.id

        # Same ID returns same session
        s1_again = server._get_or_create_session(s1.id)
        assert s1_again is s1
        assert len(server.sessions) == 2


# ══════════════════════════════════════════════════════════════════════
# Gateway Tests (Telegram + Discord)
# ══════════════════════════════════════════════════════════════════════

class TestDiscordGateway:
    """Test Discord bot gateway."""

    def test_module_imports(self):
        from terry.server.gateways import discord_gateway
        assert hasattr(discord_gateway, "DiscordGateway")
        assert hasattr(discord_gateway, "DiscordGateway")

    def test_init(self):
        from terry.server.gateways.discord_gateway import DiscordGateway

        gw = DiscordGateway(token="test_token", agent_factory=lambda: MagicMock())
        assert gw.token == "test_token"
        assert gw._running is False


class TestTelegramGateway:
    """Test Telegram bot gateway."""

    def test_module_imports(self):
        from terry.server.gateways import telegram_gateway
        assert hasattr(telegram_gateway, "TelegramGateway")
        assert hasattr(telegram_gateway, "TelegramGateway")

    def test_init(self):
        from terry.server.gateways.telegram_gateway import TelegramGateway

        gw = TelegramGateway(token="test_bot_token", agent_factory=lambda: MagicMock())
        assert gw.token == "test_bot_token"
        assert gw._running is False

    def test_init_with_agent_factory(self):
        from terry.server.gateways.telegram_gateway import TelegramGateway

        factory = lambda: MagicMock()
        gw = TelegramGateway(token="test_token", agent_factory=factory)
        assert gw.token == "test_token"
        assert gw.agent_factory is factory


# ══════════════════════════════════════════════════════════════════════
# Security Middleware Integration Tests
# ══════════════════════════════════════════════════════════════════════

class TestSecurityServerIntegration:
    """Test security middleware integration with servers."""

    def test_webui_security_disabled(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999, enable_security=False)
        assert server.security is None

    def test_webui_security_enabled_defaults(self):
        from terry.webui.server import WebUIServer

        server = WebUIServer(host="127.0.0.1", port=9999)
        assert server.security is not None

        # Validate rate limiter
        assert server.security.rate_limiter.max_requests == 100
        assert server.security.rate_limiter.window_seconds == 60

        # Validate CORS
        headers = server.security.cors.get_headers("http://example.com")
        assert "Access-Control-Allow-Methods" in headers

