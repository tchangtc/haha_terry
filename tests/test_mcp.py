"""Tests for the MCP client (terry/mcp/__init__.py).

Network- and subprocess-free: ``shutil.which`` / ``subprocess.Popen`` /
``httpx.get`` are monkeypatched so connection logic is deterministic. The
``MCPToolWrapper`` execution and schema-defaulting paths are exercised directly.
"""

from __future__ import annotations

import json

from terry.mcp import MCPClient, MCPToolWrapper


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def flush(self) -> None:
        pass


class _FakeStdout:
    """Replays framed JSON-RPC responses line-by-line, matching _rpc's parsing.

    For each queued response, it yields the ``Content-Length`` header line,
    the blank ``\\r\\n`` separator, then makes the body available for
    ``read(content_length)``.
    """

    def __init__(self, responses: list) -> None:
        self._queue: list[bytes] = []
        for r in responses:
            body = json.dumps(r).encode()
            self._queue.append(f"Content-Length: {len(body)}\r\n".encode())
            self._queue.append(b"\r\n")
            self._queue.append(body)

    def readline(self) -> bytes:
        if not self._queue:
            return b""
        return self._queue.pop(0)

    def read(self, n: int) -> bytes:
        out = b""
        while n > 0 and self._queue:
            chunk = self._queue.pop(0)
            if len(chunk) > n:
                self._queue.insert(0, chunk[n:])
                out += chunk[:n]
                n = 0
            else:
                out += chunk
                n -= len(chunk)
        return out


class _FakeProc:
    def __init__(self, responses: list | None = None, stdin: _FakeStdin | None = None) -> None:
        self.stdin = stdin or _FakeStdin()
        self.stdout = _FakeStdout(responses or [])
        self.stderr = _FakeStdout([])
        self.terminated = 0

    def terminate(self) -> None:
        self.terminated += 1


# ── MCPToolWrapper ──────────────────────────────────────────────────


class TestMCPToolWrapper:
    def test_init_prefixes_name_and_reads_schema(self):
        w = MCPToolWrapper({"name": "search", "description": "search web",
                            "inputSchema": {"type": "object", "x": 1}})
        assert w.name == "mcp_search"
        assert w.description == "search web"
        assert w.input_schema == {"type": "object", "x": 1}

    def test_init_defaults_when_missing_fields(self):
        w = MCPToolWrapper({})
        assert w.name == "mcp_unknown"
        assert w.description == "MCP tool"
        assert w.input_schema["type"] == "object"
        assert w.input_schema["properties"] == {}
        assert w.input_schema["required"] == []

    def test_execute_without_server(self):
        w = MCPToolWrapper({"name": "x"})
        out = w.execute(a=1)
        assert "not connected" in out
        assert "mcp_x" in out

    def test_execute_calls_server_call_tool(self):
        class FakeServer:
            def __init__(self) -> None:
                self.calls: list = []

            def call_tool(self, name, kwargs):
                self.calls.append((name, kwargs))
                return "result-data"

        srv = FakeServer()
        w = MCPToolWrapper({"name": "x"}, server=srv)
        assert w.execute(a=1) == "result-data"
        assert srv.calls == [("x", {"a": 1})]

    def test_execute_handles_server_exception(self):
        class FakeServer:
            def call_tool(self, name, kwargs):
                raise RuntimeError("nope")

        w = MCPToolWrapper({"name": "x"}, server=FakeServer())
        out = w.execute()
        assert "Error executing" in out
        assert "nope" in out


# ── MCPClient construction ──────────────────────────────────────────


class TestMCPClientInit:
    def test_empty_state(self):
        c = MCPClient()
        assert c.connections == {}
        assert c.wrapped_tools == []


# ── connect_stdio ───────────────────────────────────────────────────


class TestConnectStdio:
    def test_command_not_on_path(self):
        c = MCPClient()
        assert c.connect_stdio("n", "definitely-not-a-real-binary-xyz-123") is False
        assert "n" not in c.connections

    def test_success_stores_connection(self, monkeypatch):
        c = MCPClient()
        # connect_stdio sends an initialize request via _rpc; the fake stdout
        # must reply with a framed initialize result so _rpc returns non-None.
        proc = _FakeProc(responses=[{"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}])
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/fake")
        monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: proc)
        assert c.connect_stdio("n", "fake", ["--flag"]) is True
        conn = c.connections["n"]
        assert conn["type"] == "stdio"
        assert conn["command"] == "fake"
        assert conn["args"] == ["/usr/bin/fake", "--flag"]

    def test_no_initialize_response_returns_false(self, monkeypatch):
        # _rpc returns None when stdout yields no framed response → connect fails.
        c = MCPClient()
        proc = _FakeProc(responses=[])  # no response → readline returns b""
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/fake")
        monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: proc)
        assert c.connect_stdio("n", "fake") is False
        assert "n" not in c.connections

    def test_absolute_path_resolved(self, monkeypatch):
        c = MCPClient()
        resolved_path = "/opt/some/mcp-server"
        captured: list = []

        proc = _FakeProc(responses=[{"jsonrpc": "2.0", "id": 1, "result": {}}])

        def fake_which(cmd):
            captured.append(cmd)
            return resolved_path

        monkeypatch.setattr("shutil.which", fake_which)
        monkeypatch.setattr("subprocess.Popen", lambda *_a, **_k: proc)
        # A path containing "/" takes the resolved-or-command branch.
        assert c.connect_stdio("n", "/opt/some/mcp-server") is True
        assert c.connections["n"]["args"][0] == resolved_path


# ── connect_sse ─────────────────────────────────────────────────────


class TestConnectSse:
    def test_success_200(self, monkeypatch):
        c = MCPClient()

        class FakeResp:
            status_code = 200

        monkeypatch.setattr("httpx.get", lambda url, timeout=None: FakeResp())
        assert c.connect_sse("s", "http://example/sse") is True
        assert c.connections["s"] == {"type": "sse", "url": "http://example/sse"}

    def test_non_200_returns_false(self, monkeypatch):
        # connect_sse stores the connection optimistically, then returns False
        # when the initial GET is not 200 (source: mcp/__init__.py connect_sse).
        c = MCPClient()

        class FakeResp:
            status_code = 404

        monkeypatch.setattr("httpx.get", lambda url, timeout=None: FakeResp())
        assert c.connect_sse("s", "http://example/sse") is False

    def test_network_exception_returns_false(self, monkeypatch):
        c = MCPClient()

        def boom(url, timeout=None):
            raise RuntimeError("net err")

        monkeypatch.setattr("httpx.get", boom)
        assert c.connect_sse("s", "http://example/sse") is False


# ── register / list / disconnect ────────────────────────────────────


class TestRegistryOps:
    def test_register_unknown_returns_zero(self):
        assert MCPClient().register_tools("nope") == 0

    def test_register_stdio_lists_and_wraps_tools(self, monkeypatch):
        c = MCPClient()
        proc = _FakeProc(responses=[
            {"jsonrpc": "2.0", "id": 1, "result": {"tools": [
                {"name": "search", "description": "search the web",
                 "inputSchema": {"type": "object"}},
                {"name": "fetch", "description": "fetch a url"},
            ]}},
        ])
        c.connections["s"] = {"type": "stdio", "process": proc}
        assert c.register_tools("s") == 2
        names = [w.name for w in c.wrapped_tools]
        assert names == ["mcp_search", "mcp_fetch"]
        # Idempotent: a second list response with the same tools adds nothing.
        second = {"jsonrpc": "2.0", "id": 2, "result": {"tools": [
            {"name": "search", "description": "search the web"},
        ]}}
        body = json.dumps(second).encode()
        proc.stdout._queue = [
            f"Content-Length: {len(body)}\r\n".encode(), b"\r\n", body,
        ]
        assert c.register_tools("s") == 0
        assert len(c.wrapped_tools) == 2

    def test_register_sse_queries_server(self, monkeypatch):
        c = MCPClient()
        c.connections["s"] = {"type": "sse", "url": "http://example/sse"}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"jsonrpc": "2.0", "id": 1, "result": {"tools": [
                    {"name": "ping", "description": "ping"},
                ]}}

        monkeypatch.setattr("httpx.post", lambda url, json=None, timeout=None: FakeResp())
        assert c.register_tools("s") == 1
        assert c.wrapped_tools[0].name == "mcp_ping"

    def test_register_empty_tool_list_returns_zero(self, monkeypatch):
        c = MCPClient()
        proc = _FakeProc(responses=[{"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}])
        c.connections["s"] = {"type": "stdio", "process": proc}
        assert c.register_tools("s") == 0

    def test_register_no_server_response_returns_zero(self, monkeypatch):
        c = MCPClient()
        proc = _FakeProc(responses=[])  # _rpc returns None
        c.connections["s"] = {"type": "stdio", "process": proc}
        assert c.register_tools("s") == 0

    def test_call_tool_routes_to_stdio_connection(self, monkeypatch):
        c = MCPClient()
        proc = _FakeProc(responses=[
            {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "echo"}]}},
            {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "hi"}]}},
        ])
        c.connections["s"] = {"type": "stdio", "process": proc}
        c.register_tools("s")
        result = c.call_tool("echo", {"msg": "hi"})
        assert result == {"content": [{"type": "text", "text": "hi"}]}

    def test_call_tool_unknown_returns_none(self):
        assert MCPClient().call_tool("nope", {}) is None

    def test_list_connections(self):
        c = MCPClient()
        c.connections["a"] = {"type": "stdio", "process": None}
        c.connections["b"] = {"type": "sse", "url": "u"}
        conns = c.list_connections()
        assert {"name": "a", "type": "stdio"} in conns
        assert {"name": "b", "type": "sse"} in conns
        assert len(conns) == 2

    def test_disconnect_missing_returns_false(self):
        assert MCPClient().disconnect("nope") is False

    def test_disconnect_sse(self):
        c = MCPClient()
        c.connections["s"] = {"type": "sse", "url": "u"}
        assert c.disconnect("s") is True
        assert "s" not in c.connections

    def test_disconnect_stdio_terminates_process(self):
        c = MCPClient()
        terminated = []

        class FakeProc:
            def terminate(self):
                terminated.append(True)

        c.connections["p"] = {"type": "stdio", "process": FakeProc()}
        assert c.disconnect("p") is True
        assert terminated == [True]
        assert "p" not in c.connections
