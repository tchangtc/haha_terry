"""MCP (Model Context Protocol) client for Terry.

Supports connecting to MCP servers via stdio and SSE transports,
and wrapping their tools as Terry BaseTool instances.
"""

from __future__ import annotations

import subprocess
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
        # `server` is the owning MCPClient; the connection dict is resolved at
        # call time via _connection_for_tool so the wrapper is self-contained.
        self._server = server
        self._server_connection = None

    def execute(self, **kwargs) -> str:
        """Execute the MCP tool via the owning MCPClient."""
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
            import shutil

            # Validate command is a known executable on PATH
            if "/" in command or "\\" in command:
                # Absolute/relative path — must resolve to an existing file
                resolved = shutil.which(command) or command
            else:
                resolved = shutil.which(command)
                if not resolved:
                    raise ValueError(f"Command not found on PATH: {command}")

            full_args = [resolved] + (args or [])
            process = subprocess.Popen(
                full_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Send initialize request and keep the streams open (do NOT use
            # communicate(), which closes stdin/stdout after one exchange).
            init_result = self._rpc(process, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "terry", "version": __version__},
            })
            if init_result is None:
                process.terminate()
                return False

            # Notify initialized, then we're ready for tools/list and tools/call.
            self._notify(process, "initialized", {})

            self.connections[name] = {
                "type": "stdio",
                "process": process,
                "command": command,
                "args": full_args,
            }
            return True

        except Exception:
            return False

    def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on a connected MCP server.

        Resolves the connection that owns the given tool name. Stdio servers
        use a persistent request/response stream; SSE servers POST JSON-RPC.
        Returns the raw ``result`` field of the server's response, or None.
        """
        conn = self._connection_for_tool(name)
        if conn is None:
            return None
        if conn["type"] == "stdio":
            return self._rpc(conn["process"], "tools/call", {
                "name": name, "arguments": arguments,
            })
        # SSE
        import httpx
        resp = httpx.post(
            conn["url"], json=self._build_request("tools/call", {
                "name": name, "arguments": arguments,
            }), timeout=30,
        )
        return resp.json().get("result") if resp.status_code == 200 else None

    def _connection_for_tool(self, tool_name: str) -> dict | None:
        """Find the connection that registered the given tool name."""
        for w in self.wrapped_tools:
            if w._mcp_tool.get("name") == tool_name:
                return w._server_connection
        return None

    @staticmethod
    def _build_request(method: str, params: dict) -> dict:
        return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    def _rpc(self, process: subprocess.Popen, method: str, params: dict) -> Any:
        """Send a JSON-RPC request over stdio with Content-Length framing and
        return the ``result`` field of the response, or None on failure."""
        import json
        if not process.stdin or not process.stdout:
            return None
        body = json.dumps(self._build_request(method, params))
        try:
            process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
            process.stdin.flush()
            return self._read_rpc_response(process)
        except Exception:
            return None

    def _notify(self, process: subprocess.Popen, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        import json
        if not process.stdin:
            return
        body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
        try:
            process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
            process.stdin.flush()
        except Exception:
            pass

    @staticmethod
    def _read_rpc_response(process: subprocess.Popen) -> Any:
        """Read one Content-Length-framed JSON-RPC response and return its
        ``result`` field."""
        import json
        content_length = 0
        while True:
            line = process.stdout.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
        if content_length <= 0:
            return None
        body = process.stdout.read(content_length)
        try:
            return json.loads(body).get("result")
        except Exception:
            return None

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

            # Attempt initial connection
            response = httpx.get(url, timeout=10)
            if response.status_code != 200:
                return False

            self.connections[name] = {
                "type": "sse",
                "url": url,
            }
            return True

        except Exception:
            return False

    def register_tools(self, name: str) -> int:
        """Register MCP server tools as Terry tools.

        Calls ``tools/list`` on the named connection and wraps each advertised
        tool as an :class:`MCPToolWrapper`. Idempotent — tools already wrapped
        for this connection are not duplicated.

        Args:
            name: Connection name

        Returns:
            Number of tools registered for this connection
        """
        conn = self.connections.get(name)
        if conn is None:
            return 0

        # Query the server for its tool catalogue.
        if conn["type"] == "stdio":
            result = self._rpc(conn["process"], "tools/list", {})
        else:  # sse
            import httpx
            try:
                resp = httpx.post(conn["url"], json=self._build_request("tools/list", {}), timeout=30)
                result = resp.json().get("result") if resp.status_code == 200 else None
            except Exception:
                result = None

        if not result or not isinstance(result, dict):
            return 0

        advertised = result.get("tools", [])
        existing = {w._mcp_tool.get("name") for w in self.wrapped_tools if w._server_connection is conn}
        added = 0
        for tool in advertised:
            if tool.get("name") in existing:
                continue
            wrapper = MCPToolWrapper(tool, server=self)
            wrapper._server_connection = conn
            self.wrapped_tools.append(wrapper)
            added += 1
        return added

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
