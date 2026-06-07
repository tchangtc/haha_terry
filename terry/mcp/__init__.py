"""MCP (Model Context Protocol) client for Terry.

Supports connecting to MCP servers via stdio and SSE transports,
and wrapping their tools as Terry BaseTool instances.
"""

from __future__ import annotations

from typing import Any

from terry import __version__

from ..tools import BaseTool


class MCPToolWrapper(BaseTool):
    """Wraps an MCP tool as a Terry BaseTool."""

    def __init__(self, mcp_tool: dict, server: Any = None):
        self.name = f"mcp_{mcp_tool.get('name', 'unknown')}"
        self.description = mcp_tool.get("description", "MCP tool")
        self.input_schema = mcp_tool.get("inputSchema", {
            "type": "object",
            "properties": {},
            "required": [],
        })
        self._mcp_tool = mcp_tool
        self._server = server

    def execute(self, **kwargs) -> str:
        """Execute the MCP tool via the server."""
        if not self._server:
            return f"Error: MCP server not connected for tool '{self.name}'"

        try:
            result = self._server.call_tool(self._mcp_tool.get("name", ""), kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing MCP tool '{self.name}': {e}"


class MCPClient:
    """Minimal MCP client for connecting to external tool servers.

    Uses subprocess for stdio transport and httpx for SSE transport.
    Does NOT require the 'mcp' pip package — implements the protocol directly.
    """

    def __init__(self):
        self.connections: dict[str, Any] = {}
        self.wrapped_tools: list[MCPToolWrapper] = []

    def connect_stdio(self, name: str, command: str, args: list[str] | None = None) -> bool:
        """Connect to an MCP server via stdio (subprocess).

        Args:
            name: Connection name
            command: Executable path
            args: Command arguments

        Returns:
            True if connected successfully
        """
        try:
            import json
            import subprocess

            full_args = [command] + (args or [])
            process = subprocess.Popen(
                full_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Send initialize request
            init_request = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "terry", "version": __version__},
                },
            })

            stdout, stderr = process.communicate(
                input=init_request + "\n", timeout=10
            )

            if process.returncode != 0 and process.returncode is not None:
                return False

            self.connections[name] = {
                "type": "stdio",
                "process": process,
                "command": command,
                "args": full_args,
            }

            # Load tools from the server
            json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            })

            # For stdio, we need to restart the process and use proper I/O
            # This is a simplified implementation
            return True

        except Exception:
            return False

    def connect_sse(self, name: str, url: str) -> bool:
        """Connect to an MCP server via SSE transport.

        Args:
            name: Connection name
            url: SSE endpoint URL

        Returns:
            True if connected
        """
        try:
            import httpx

            self.connections[name] = {
                "type": "sse",
                "url": url,
            }

            # Attempt initial connection
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                return True
            return False

        except Exception:
            return False

    def register_tools(self, name: str) -> int:
        """Register MCP server tools as Terry tools.

        Args:
            name: Connection name

        Returns:
            Number of tools registered
        """
        if name not in self.connections:
            return 0

        self.connections[name]

        # In a full implementation, we'd call tools/list via the MCP protocol
        # and register each tool. For now, provide the framework.
        # The actual tool registration happens when the server responds.

        return len(self.wrapped_tools)

    def list_connections(self) -> list[dict[str, str]]:
        """List all MCP connections."""
        return [
            {"name": name, "type": conn["type"]}
            for name, conn in self.connections.items()
        ]

    def disconnect(self, name: str) -> bool:
        """Disconnect from an MCP server."""
        if name not in self.connections:
            return False
        conn = self.connections.pop(name)
        if conn["type"] == "stdio":
            try:
                conn["process"].terminate()
            except Exception:
                pass
        return True
