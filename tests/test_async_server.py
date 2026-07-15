"""Tests for the async FastAPI server (terry/server/async_server.py).

Driven through Starlette's TestClient — the real ASGI app with routing,
validation, and error handling, but no network. Security middleware is disabled
so the tests focus on routing/handler logic.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from terry.server.async_server import (
    AsyncTerryServer,
    ChatRequest,
    ChatResponse,
    create_async_server,
)


class _Tools:
    def execute(self, name, **kwargs):
        return f"ran {name} with {kwargs}"


class FakeAgent:
    def __init__(self):
        self.tools = _Tools()

    def run(self, message):
        return f"echo: {message}"


class FakeManager:
    async def spawn(self, prompt, timeout):
        return "agent-123"

    async def wait(self, agent_id, timeout):
        return "done"

    def get_status(self, agent_id):
        return {"status": "completed", "error": None}

    async def cancel(self, agent_id):
        return True


def _client(with_agent=True, with_manager=False):
    server = AsyncTerryServer(enable_security=False)
    if with_agent:
        server.set_agent_factory(FakeAgent)
    if with_manager:
        server.set_sub_agent_manager(FakeManager())
    return TestClient(server.app), server


class TestModels:
    def test_chat_request_defaults(self):
        req = ChatRequest(message="hi")
        assert req.message == "hi"
        assert req.session_id is None

    def test_chat_response_roundtrip(self):
        resp = ChatResponse(response="ok", session_id="s1", duration_seconds=0.5)
        assert resp.response == "ok" and resp.session_id == "s1"


class TestStatus:
    def test_status_ok(self):
        client, _ = _client()
        r = client.get("/status")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "running"
        assert "version" in body


class TestChat:
    def test_chat_without_agent_503(self):
        client, _ = _client(with_agent=False)
        r = client.post("/chat", json={"message": "hi"})
        assert r.status_code == 503

    def test_chat_echoes_response(self):
        client, _ = _client()
        r = client.post("/chat", json={"message": "hello"})
        assert r.status_code == 200
        body = r.json()
        assert body["response"] == "echo: hello"
        assert body["session_id"]

    def test_chat_reuses_session(self):
        client, server = _client()
        r1 = client.post("/chat", json={"message": "a"})
        sid = r1.json()["session_id"]
        client.post("/chat", json={"message": "b", "session_id": sid})
        assert sid in server._sessions

    def test_chat_stream_sync_agent(self):
        client, _ = _client()
        r = client.post("/chat/stream", json={"message": "stream me"})
        assert r.status_code == 200
        assert "stream me" in r.text
        assert "[DONE]" in r.text


class TestTools:
    def test_tool_without_agent_503(self):
        client, _ = _client(with_agent=False)
        r = client.post("/tools/bash", json={"tool_name": "bash", "arguments": {}})
        assert r.status_code == 503

    def test_tool_executes(self):
        client, _ = _client()
        r = client.post("/tools/bash", json={"tool_name": "bash", "arguments": {"cmd": "ls"}})
        assert r.status_code == 200
        assert "ran bash" in r.json()["result"]


class TestSubAgent:
    def test_spawn_without_manager_503(self):
        client, _ = _client(with_manager=False)
        r = client.post("/subagent/spawn", json={"prompt": "do it"})
        assert r.status_code == 503

    def test_spawn_and_wait(self):
        client, _ = _client(with_manager=True)
        r = client.post("/subagent/spawn", json={"prompt": "do it"})
        assert r.status_code == 200
        assert r.json()["agent_id"] == "agent-123"

        r2 = client.post("/subagent/agent-123/wait")
        assert r2.status_code == 200
        assert r2.json()["status"] == "completed"

    def test_status_and_cancel(self):
        client, _ = _client(with_manager=True)
        assert client.get("/subagent/agent-123/status").json()["status"] == "completed"
        assert client.post("/subagent/agent-123/cancel").json()["success"] is True


class TestFactory:
    def test_create_async_server(self):
        server = create_async_server()
        assert isinstance(server, AsyncTerryServer)
        assert server.app is not None
